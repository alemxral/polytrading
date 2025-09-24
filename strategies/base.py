class Strategy:
    def on_message(self, message):
        raise NotImplementedError

    def on_tick(self):
        pass
