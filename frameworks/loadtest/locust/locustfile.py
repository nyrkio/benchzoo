"""Minimal Locust scenario: simulated users hammer the nginx homepage."""
from locust import HttpUser, task


class HomepageUser(HttpUser):
    host = "http://localhost:8080"

    @task
    def homepage(self):
        self.client.get("/")
