import requests
import time
import logging
import re
from typing import Optional, Tuple

GEMINI_API_KEY = "AIzaSyAbxBS3LrF99lk2x3eifeYo9hqAfB-3bR8"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# Database field length limits
MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 200 
MAX_SUMMARY_LENGTH = 100   
MAX_REVIEW_LENGTH = 100   

# Set up logging
logging.basicConfig(level=logging.INFO)

def truncate_text(text: str, max_length: int, add_ellipsis: bool = True) -> str:
    """
    Truncate text to specified length, optionally adding ellipsis.
    Tries to break at a sentence or word boundary when possible.
    """
    if len(text) <= max_length:
        return text
        
    # If we need to truncate, leave room for ellipsis
    if add_ellipsis:
        max_length -= 3
        
    # Try to break at a sentence first
    sentences = text[:max_length].split('.')
    if len(sentences) > 1:
        truncated = '.'.join(sentences[:-1]) + '.'
    else:
        # If no sentence break, try to break at a word boundary
        words = text[:max_length].split()
        truncated = ' '.join(words[:-1])
        
    if add_ellipsis:
        truncated += '...'
        
    return truncated

def extract_first_title(text: str) -> str:
    """Extract the first concrete title from the response, skipping explanatory text."""
    # Look for text between asterisks or after a bullet point
    patterns = [
        r'\*\*(.*?)\*\*',  # Text between double asterisks
        r'\* (.*?)(?=\(|$)',  # Text after bullet point, before optional parentheses or end of line
        r'\n(.*?)(?=\n|$)'  # Any line that might be a title
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.MULTILINE)
        if matches:
            # Get first match and clean it up
            title = matches[0].strip()
            if title and not title.startswith(('Here', 'More', 'The best')):
                return truncate_text(title, MAX_TITLE_LENGTH, add_ellipsis=False)
    
    # If no good match found, return the first line that's not empty or explanatory
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    for line in lines:
        if not line.startswith(('Here', 'More', 'The best')):
            return truncate_text(line, MAX_TITLE_LENGTH, add_ellipsis=False)
    
    raise ValueError("Could not extract a valid title from the response")

def parse_rating_review(text: str) -> Tuple[float, str]:
    """
    Parse rating and review from the API response.
    Returns a tuple of (rating, review)
    """
    try:
        # Extract rating (assuming format includes "Rating: X" or similar)
        rating_match = re.search(r'Rating:\s*(\d+\.?\d*)', text)
        if not rating_match:
            raise ValueError("No rating found in response")
        rating = float(rating_match.group(1))
        
        # Extract review (assuming format includes "Review: ..." or similar)
        review_match = re.search(r'Review:(.*?)(?=Rating:|$)', text, re.DOTALL)
        if not review_match:
            raise ValueError("No review found in response")
        review = review_match.group(1).strip()
        
        # Validate rating range
        if not 0 <= rating <= 5:
            raise ValueError(f"Rating {rating} is out of range (0-5)")
            
        # Truncate review if needed
        review = truncate_text(review, MAX_REVIEW_LENGTH)
        
        return rating, review
        
    except (ValueError, AttributeError) as e:
        logging.error(f"Failed to parse rating/review: {str(e)}")
        raise ValueError(f"Failed to parse rating/review: {str(e)}")

def interact_with_gemini(prompt: str, extract_title: bool = False, content_type: str = None) -> str:
    """
    Interact with the Gemini API with improved response parsing and length validation.
    
    Args:
        prompt: The text prompt to send to Gemini
        extract_title: If True, attempts to extract a single title from a list of suggestions
        content_type: Type of content being generated ('title', 'description', 'summary', 'review')
                     Used for applying appropriate length limits
    """
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    retries = 5
    
    for attempt in range(retries):
        try:
            response = requests.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logging.info(f"Gemini API raw response: {data}")
                    
                    if "candidates" in data and data["candidates"]:
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        
                        if extract_title:
                            return extract_first_title(text)
                            
                        # Apply appropriate length limits based on content type
                        if content_type == 'description':
                            return truncate_text(text, MAX_DESCRIPTION_LENGTH)
                        elif content_type == 'summary':
                            return truncate_text(text, MAX_SUMMARY_LENGTH)
                        elif content_type == 'review':
                            return truncate_text(text, MAX_REVIEW_LENGTH)
                        else:
                            return text
                    else:
                        logging.error(f"Unexpected response structure: {data}")
                        raise ValueError("Unexpected response format from Gemini API")
                
                except (ValueError, KeyError) as e:
                    logging.error(f"Failed to parse Gemini API response: {e}")
                    raise ValueError("Unexpected response format from Gemini API")
            
            elif response.status_code in (503, 429):
                wait_time = 2 ** attempt
                logging.warning(
                    f"Status {response.status_code}, retrying in {wait_time}s "
                    f"(attempt {attempt + 1}/{retries})..."
                )
                time.sleep(wait_time)
            
            else:
                logging.error(f"Gemini API error: {response.status_code} - {response.text}")
                raise ValueError(
                    f"Gemini API call failed with status code {response.status_code}: {response.text}"
                )
        
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error: {str(e)}")
            if attempt == retries - 1:
                raise ValueError(f"Max retries exceeded: {str(e)}")
            time.sleep(2 ** attempt)
            continue
    
    raise ValueError("Gemini API call failed after multiple retries.")


