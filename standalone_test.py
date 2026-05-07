from textual.app import App
from textual.widgets import Label

class StandaloneApp(App):
    def compose(self):
        yield Label("HELLO WORLD FROM STANDALONE APP")

if __name__ == "__main__":
    StandaloneApp().run()
