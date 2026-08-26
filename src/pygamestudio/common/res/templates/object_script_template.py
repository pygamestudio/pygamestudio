class NewScript:
    def __init__(self, owner):
        self.owner = owner
    
    def on_start(self):
        ...

    def on_update(self, delta_time):
        pass
    
    def on_destroy(self):
        pass