import pytest


def test_get_url_stats(client):
    """Test retrieving URL statistics."""
    # Create short URL
    create_response = client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/stats"}
    )
    short_code = create_response.json()["short_code"]
    
    # Get stats
    response = client.get(f"/api/v1/admin/stats/{short_code}")
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://example.com/stats"
    assert data["short_code"] == short_code
    assert data["click_count"] == 0
    assert "created_at" in data


def test_get_url_stats_not_found(client):
    """Test getting stats for non-existent URL."""
    response = client.get("/api/v1/admin/stats/nonexistent")
    assert response.status_code == 404


def test_list_urls_empty(client):
    """Test listing URLs when database is empty."""
    response = client.get("/api/v1/admin/list")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["urls"] == []


def test_list_urls_with_data(client, sample_urls):
    """Test listing URLs with pagination."""
    # Create multiple URLs
    for url in sample_urls:
        client.post("/api/v1/shorten", json={"url": url})
    
    # List all URLs
    response = client.get("/api/v1/admin/list?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(sample_urls)
    assert len(data["urls"]) == len(sample_urls)


def test_list_urls_pagination(client):
    """Test URL listing pagination."""
    # Create 5 URLs
    for i in range(5):
        client.post("/api/v1/shorten", json={"url": f"https://example.com/test{i}"})
    
    # Get first page (2 items)
    response = client.get("/api/v1/admin/list?skip=0&limit=2")
    data = response.json()
    assert data["total"] == 5
    assert len(data["urls"]) == 2
    assert data["skip"] == 0
    assert data["limit"] == 2
    
    # Get second page (2 items)
    response = client.get("/api/v1/admin/list?skip=2&limit=2")
    data = response.json()
    assert len(data["urls"]) == 2
    assert data["skip"] == 2


def test_total_clicks_zero(client):
    """Test total clicks with no data."""
    response = client.get("/api/v1/admin/analytics/total_clicks")
    assert response.status_code == 200
    assert response.json()["total_clicks"] == 0


def test_admin_endpoints_exempt_from_rate_limit(client):
    """Test that admin endpoints are not rate limited."""
    # Make 150 requests to admin endpoint (more than default limit)
    for _ in range(150):
        response = client.get("/api/v1/admin/analytics/total_clicks")
        assert response.status_code == 200
