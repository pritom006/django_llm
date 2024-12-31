from django.db import models

class Property(models.Model):
    hotel_id = models.CharField(max_length=100, unique=True)  # Reference for scraped data
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    price = models.CharField(max_length=50, blank=True, null=True)

class Summary(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='summaries')
    summary = models.TextField()

class PropertyRating(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    rating = models.FloatField()
    review = models.TextField()