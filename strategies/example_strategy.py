from .base import Strategy

class ExampleStrategy(Strategy):
    def on_message(self, message):
        print(f"Received message: {message}")
