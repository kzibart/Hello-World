import arcade
import asyncio
import sys
import random

# --- Constants ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 760
CARD_WIDTH = 100
CARD_HEIGHT = CARD_WIDTH * 1.4
CARD_LABEL_OFFSET_X = CARD_WIDTH * 0.075
CARD_LABEL_OFFSET_Y = CARD_WIDTH * 0.03
SCREEN_TITLE = "Virtual Deck of Cards"
DECK_POS_X = 200
DECK_POS_Y = 200
DECK_GRID_X = CARD_WIDTH / 4
DECK_GRID_Y = CARD_HEIGHT / 4

class Card:
    def __init__(self, x, y, suit, value):
        self.x = x
        self.y = y
        self.suit = suit
        self.value = value
        self.width = CARD_WIDTH
        self.height = CARD_HEIGHT
        if self.suit == "♠" or self.suit == "♣":
            self.color = arcade.color.BLACK
        else:
            self.color = arcade.color.RED
        self.face_up = False

        self.top_label = arcade.Text(
            str(self.value),
            self.x - (self.width / 2) + CARD_LABEL_OFFSET_X,
            self.y + (self.height / 2) - CARD_LABEL_OFFSET_Y,
            self.color,
            font_size=self.width * 0.18,
            anchor_x="left",
            anchor_y="top"
        )
        self.bottom_label = arcade.Text(
            str(self.value),
            self.x + (self.width / 2) - CARD_LABEL_OFFSET_X,
            self.y - (self.height / 2) + CARD_LABEL_OFFSET_Y,
            self.color,
            font_size=self.width * 0.18,
            anchor_x="right",
            anchor_y="bottom"
        )

        self.center_suit = arcade.Text(
            self.suit,
            self.x,
            self.y,
            self.color,
            font_size=self.width * 0.35,
            anchor_x="center",
            anchor_y="center"
        )

    def draw(self):
        self.top_label.x = self.x - (self.width / 2) + CARD_LABEL_OFFSET_X
        self.top_label.y = self.y + (self.height / 2) - CARD_LABEL_OFFSET_Y
        self.bottom_label.x = self.x + (self.width / 2) - CARD_LABEL_OFFSET_X
        self.bottom_label.y = self.y - (self.height / 2) + CARD_LABEL_OFFSET_Y
        self.center_suit.x = self.x
        self.center_suit.y = self.y

        card_rect = arcade.LBWH(
            self.x - self.width / 2,
            self.y - self.height / 2,
            self.width,
            self.height
        )
        if self.face_up:
            arcade.draw_rect_filled(card_rect, color=arcade.color.WHITE)
            arcade.draw_rect_outline(card_rect, color=arcade.color.BLACK, border_width=2)
            self.top_label.draw()
            self.bottom_label.draw()
            self.center_suit.draw()
        else:
            arcade.draw_rect_filled(card_rect, color=arcade.color.BRICK_RED)
            arcade.draw_rect_outline(card_rect, color=arcade.color.WHITE, border_width=2)

class MyGame(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
        arcade.set_background_color(arcade.color.AMAZON)
        self.cards = []
        self.held_card = None
        self.hold_start_x = 0
        self.hold_start_y = 0

    def setup(self):
        for s in range(4):
            this_suit = "♠♣♦♥"[s]
            for v in range(13):
                this_value = "A23456789TJQK"[v]
                if this_value == "T":
                    this_value = "10"
                new_card = Card(
                    x=DECK_POS_X,
                    y=DECK_POS_Y,
                    suit=this_suit,
                    value=this_value
                )
                self.cards.append(new_card)
        random.shuffle(self.cards)

    def on_draw(self):
        self.clear()
        for card in self.cards:
            card.draw()

    def on_mouse_press(self, x, y, button, modifiers):
        for card in reversed(self.cards):
            left = card.x - card.width / 2
            right = card.x + card.width / 2
            bottom = card.y - card.height / 2
            top = card.y + card.height / 2
            if left <= x <= right and bottom <= y <= top:
                self.hold_start_x=x
                self.hold_start_y=y
                self.cards.remove(card)
                self.cards.append(card)
                self.held_card = card
                print(f"Clicked card {card.value}{card.suit}")
                break

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self.held_card:
            self.held_card.x = round(x / DECK_GRID_X) * DECK_GRID_X
            self.held_card.y = round(y / DECK_GRID_Y) * DECK_GRID_Y

    def on_mouse_release(self, x, y, button, modifiers):
        if not self.held_card:
            return
        dist_moved = abs(x-self.hold_start_x) + abs(y-self.hold_start_y)
        if dist_moved < 5:
            self.held_card.face_up = not self.held_card.face_up
        else:
            self.held_card.x = round(self.held_card.x / DECK_GRID_X) * DECK_GRID_X
            self.held_card.y = round(self.held_card.y / DECK_GRID_Y) * DECK_GRID_Y

        self.held_card = None
        
    def on_close(self):
        super().on_close()

async def main():
    window = MyGame()
    window.setup()
    
    # This is the manual "Engine Room"
    while not window.has_exit:
        # 1. Process mouse/keyboard events
        window.dispatch_events()
        
        # 2. Run your update logic (60 times a second)
        window.on_update(1/60)
        
        # 3. Clear the screen and draw the cards
        window.clear() # This is the missing piece that "unfreezes" the screen!
        window.on_draw()
        
        # 4. Flip the buffer to show the new frame on your monitor
        window.flip()
        
        # 5. Yield to the Browser/OS (Crucial for Pygbag)
        await asyncio.sleep(1/60)
    window.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass