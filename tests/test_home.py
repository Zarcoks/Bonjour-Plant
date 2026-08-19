import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_index_page(client):
    response = client.get(reverse("plant_management_index"))
    assert response.status_code == 200
    assert b"Bonjour Plant" in response.content
