from django.contrib import admin
from .models import Property,Summary,PropertyRating
# Register your models here.
admin.site.register(Property)
admin.site.register(Summary)
admin.site.register(PropertyRating)