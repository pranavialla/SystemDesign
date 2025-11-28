import pytest

def test_create_short_url_success(client):
    """Test successful URL shortening."""
    response = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/test"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["url"] == "https://example.com/test"
    assert "short_code" in data
    assert len(data["short_code"]) <= 10
    assert data["short_url"].endswith(data["short_code"])
    assert data["click_count"] == 0


def test_create_short_url_idempotent(client):
    """Test that same URL returns same short code."""
    url = "https://example.com/idempotent"
    
    # Create first time
    response1 = client.post("/api/v1/shorten", json={"url": url})
    assert response1.status_code == 201
    code1 = response1.json()["short_code"]
    
    # Create second time with same URL
    response2 = client.post("/api/v1/shorten", json={"url": url})
    assert response2.status_code == 201
    code2 = response2.json()["short_code"]
    
    # Should return same short code
    assert code1 == code2


def test_create_short_url_with_custom_alias(client):
    """Test URL shortening with custom alias."""
    response = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/custom", "custom_alias": "mybrand"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["short_code"] == "mybrand"


def test_create_short_url_custom_alias_collision(client):
    """Test that duplicate custom alias returns error."""
    # Create first URL with custom alias
    client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/first", "custom_alias": "taken"}
    )
    
    # Try to create second URL with same alias
    response = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/second", "custom_alias": "taken"}
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_create_short_url_custom_alias_too_long(client):
    """Test that custom alias longer than 10 chars is rejected."""
    response = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/test", "custom_alias": "this_is_too_long"}
    )
    assert response.status_code == 422  # Pydantic validation error


def test_create_short_url_invalid_url(client):
    """Test that invalid URL format is rejected."""
    invalid_urls = [
        "not-a-url",
        "ftp://example.com",  # Wrong protocol
        "http://",  # Missing domain
    ]
    
    for invalid_url in invalid_urls:
        response = client.post("/api/v1/shorten", json={"url": invalid_url})
        assert response.status_code == 422, f"Should reject: {invalid_url}"


def test_create_short_url_too_long(client):
    """Test that URL longer than 2048 chars is rejected."""
    long_url = "https://example.com/" + "a" * 2100
    response = client.post("/api/v1/shorten", json={"url": long_url})
    assert response.status_code == 422


def test_redirect_success(client):
    """Test successful redirect."""
    # Create short URL
    create_response = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/redirect-test"}
    )
    short_code = create_response.json()["short_code"]
    
    # Test redirect
    response = client.get(f"/{short_code}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/redirect-test"


def test_redirect_not_found(client):
    """Test redirect with non-existent short code."""
    response = client.get("/nonexistent", follow_redirects=False)
    assert response.status_code == 404


def test_redirect_increments_click_count(client):
    """Test that redirects increment click count."""
    # Create short URL
    create_response = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/clicks"}
    )
    short_code = create_response.json()["short_code"]
    
    # Initial click count should be 0
    stats = client.get(f"/api/v1/admin/stats/{short_code}").json()
    assert stats["click_count"] == 0
    
    # Perform 3 redirects
    for _ in range(3):
        client.get(f"/{short_code}", follow_redirects=False)
    
    # Check click count increased
    stats = client.get(f"/api/v1/admin/stats/{short_code}").json()
    assert stats["click_count"] == 3