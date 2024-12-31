from django.core.management.base import BaseCommand
from django.db import connections, transaction
from property.models import Property, Summary, PropertyRating
from gemini.gemini_service import interact_with_gemini, parse_rating_review
import logging
import re

logging.basicConfig(level=logging.INFO)

class Command(BaseCommand):
    help = "Rewrite property titles, generate descriptions, summaries, ratings, and reviews using Gemini-1.5-Flash model."

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Number of properties to process (default: 10)'
        )
        parser.add_argument(
            '--offset',
            type=int,
            default=0,
            help='Number of properties to skip (default: 0)'
        )

    def select_best_title(self, title_response: str, original_title: str) -> str:
        """
        Select the best title from multiple suggestions.
        Prioritizes titles that:
        1. Are concise (not too long)
        2. Maintain important keywords from original title
        3. Avoid generic prefixes like "Here are" or "The best"
        """
        # Extract all suggested titles
        titles = []
        
        # Look for bulleted items
        bullet_matches = re.findall(r'\* ([^\n]+)', title_response)
        if bullet_matches:
            titles.extend(bullet_matches)
        
        # Look for titles between asterisks
        asterisk_matches = re.findall(r'\*\*(.*?)\*\*', title_response)
        if asterisk_matches:
            titles.extend(asterisk_matches)
            
        # If no structured titles found, split by newlines and clean up
        if not titles:
            titles = [line.strip() for line in title_response.split('\n')
                     if line.strip() and not line.startswith(('Here', 'The best', '#'))]

        # Remove any empty strings and duplicates
        titles = list(set([t.strip() for t in titles if t.strip()]))
        
        if not titles:
            return original_title[:100]  # Fallback to original title if no valid suggestions

        # Score each title
        scored_titles = []
        original_words = set(re.findall(r'\w+', original_title.lower()))
        
        for title in titles:
            score = 0
            
            # Prefer titles between 20-50 characters
            length = len(title)
            if 20 <= length <= 50:
                score += 2
            elif length < 70:
                score += 1
                
            # Prefer titles that maintain important keywords
            title_words = set(re.findall(r'\w+', title.lower()))
            keyword_matches = len(original_words.intersection(title_words))
            score += keyword_matches
            
            # Penalize very generic titles
            if any(title.lower().startswith(prefix) for prefix in ['welcome to', 'the', 'a ']):
                score -= 1
                
            scored_titles.append((score, title))
        
        # Sort by score and return the best title
        best_title = sorted(scored_titles, key=lambda x: (-x[0], len(x[1])))[0][1]
        return best_title[:100]  # Ensure it fits in database field

    def handle(self, *args, **options):
        limit = options['limit']
        offset = options['offset']
        
        logging.info(f"Starting processing with limit={limit}, offset={offset}")

        # Fetch properties from the `properties` table with LIMIT and OFFSET
        with connections["default"].cursor() as cursor:
            cursor.execute("""
                SELECT hotel_id, title, location, latitude, longitude, price 
                FROM properties 
                LIMIT %s OFFSET %s
            """, [limit, offset])
            properties = cursor.fetchall()

        if not properties:
            logging.info("No properties found to process.")
            return

        processed_count = 0
        for prop in properties:
            hotel_id, title, location, latitude, longitude, price = prop

            try:
                with transaction.atomic():
                    # Step 1: Create or update the Property entry first
                    property_obj, created = Property.objects.get_or_create(
                        hotel_id=hotel_id,
                        defaults={
                            'title': title,
                            'location': location,
                            'latitude': latitude,
                            'longitude': longitude,
                            'price': price
                        }
                    )

                    # Step 2: Get title suggestions and select the best one
                    title_response = interact_with_gemini(
                        f"Rewrite this title: {title}",
                        content_type='title'
                    )
                    rewritten_title = self.select_best_title(title_response, title)
                    logging.info(f"Selected title for {hotel_id}: {rewritten_title}")
                    
                    # Generate description
                    description_prompt = (
                        f"Generate a detailed description for the following property:\n"
                        f"Title: {rewritten_title}\n"
                        f"Location: {location}\nLatitude: {latitude}\nLongitude: {longitude}\nPrice: {price}"
                    )
                    rewritten_description = interact_with_gemini(
                        description_prompt,
                        content_type='description'
                    )

                    # Update the property with new title and description
                    property_obj.title = rewritten_title
                    property_obj.description = rewritten_description
                    property_obj.save()

                    # Generate and save summary
                    summary_prompt = (
                        f"Summarize the following property information:\n"
                        f"Title: {rewritten_title}\nDescription: {rewritten_description}\n"
                        f"Location: {location}\nLatitude: {latitude}\nLongitude: {longitude}\nPrice: {price}"
                    )
                    summary_text = interact_with_gemini(
                        summary_prompt,
                        content_type='summary'
                    )

                    Summary.objects.create(
                        property=property_obj,
                        summary=summary_text
                    )

                    # Generate and save rating/review
                    review_prompt = (
                        f"Generate a rating (0-5) and review for this property. Format as 'Rating: X\nReview: Your review text':\n"
                        f"Title: {rewritten_title}\nDescription: {rewritten_description}\n"
                        f"Location: {location}\nPrice: {price}"
                    )
                    review_response = interact_with_gemini(
                        review_prompt,
                        content_type='review'
                    )

                    try:
                        rating, review = parse_rating_review(review_response)
                        PropertyRating.objects.create(
                            property=property_obj,
                            rating=rating,
                            review=review
                        )
                    except ValueError as e:
                        logging.error(f"Failed to parse rating/review for hotel_id {hotel_id}: {str(e)}")

                processed_count += 1
                logging.info(f"Successfully processed hotel_id {hotel_id} ({processed_count}/{limit})")

            except Exception as e:
                logging.error(f"Error processing hotel_id {hotel_id}: {str(e)}")
                continue

        logging.info(f"Completed processing {processed_count} properties. Use --offset {offset + limit} to process the next batch.")