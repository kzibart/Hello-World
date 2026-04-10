import arcade
from arcade import shape_list
import asyncio
import sys
import math
import random
from pyglet.graphics import Batch
from datetime import datetime
from arcade.types import LBWH
from collections import deque

# --- Constants ---
DEVICE_WIDTH, DEVICE_HEIGHT = arcade.get_display_size()

SCREEN_HEIGHT = int(DEVICE_HEIGHT * 0.85)
SCREEN_WIDTH = int(SCREEN_HEIGHT * (16/9))
if SCREEN_WIDTH > DEVICE_WIDTH:
    SCREEN_WIDTH = int(DEVICE_WIDTH * 0.9)
    SCREEN_HEIGHT = int(SCREEN_WIDTH * (9/16))
print(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}")

#SCREEN_WIDTH = 1280
#SCREEN_HEIGHT = 720
SCREEN_ASPECT = SCREEN_WIDTH/SCREEN_HEIGHT

#SCREEN_WIDTH =  800
#SCREEN_HEIGHT = 1280

PHASER_DURATION = 20
ENEMY_DAMAGE_LOW = 4/PHASER_DURATION
ENEMY_DAMAGE_HIGH = 6/PHASER_DURATION
PHASER_DAMAGE_LOW = 30/PHASER_DURATION
PHASER_DAMAGE_HIGH = 40/PHASER_DURATION
TORPEDO_DAMAGE_LOW = 45
TORPEDO_DAMAGE_HIGH = 55
MAX_ENERGY = 1000
MAX_DAYS = 36
PHASER_COST = 50
MAX_REPAIR_DELAY = 3
MAX_WARP = 60    # Must be an even number
MESSAGE_DELAY = 60

TRANS = 64
BIG_FILLED = (64,64,128,TRANS)
BIG_OUTLINE = (64,64,128,255)
SMALL_FILLED = (128,128,64,TRANS)
SMALL_OUTLINE = (128,128,64,255)
STATUS_FILLED = (64,128,64,TRANS)
STATUS_OUTLINE = (64,128,64,255)
LOG_FILLED = (64,128,128,TRANS)
LOG_OUTLINE = (64,128,128,255)
INFO_FILLED = (64,64,64,TRANS)
INFO_OUTLINE = (64,64,64,255)
BUTTON_FILLED = (128,64,0,TRANS*2)
BUTTON_OUTLINE = (128,64,0,255)

INFO_MESSSAGE_COLOR = (255,255,255,255)
WARNING_MESSAGE_COLOR = (255,255,64,255)
ALERT_MESSAGE_COLOR = (255,64,64,255)
GOOD_MESSAGE_COLOR = (64,255,64,255)

PHASER_COLOR = arcade.color.RED_ORANGE
ENEMY_COLOR = arcade.color.GREEN
BASE_COLOR = arcade.color.BLUE
FOG_COLOR = (*arcade.color.LIGHT_GRAY[:3], TRANS)
GRIDLINE_WIDTH = 3
SUBGRID_WIDTH = 1


print(f"Device size: {DEVICE_WIDTH},{DEVICE_HEIGHT}")
print(f"Screen size: {SCREEN_WIDTH},{SCREEN_HEIGHT}")

# Define areas as (left point, bottom point, width, height) based on a 16x9 grid
#Horizontal orientation:
HRATIO = (16,9)
HBIG = (0,2,7,7)
HNAV = (0,0,1.75,1.75)
HTORP = (1.75,0,1.75,1.75)
HPHASER = (3.5,0,1.75,1.75)
HREPAIR = (5.25,0,1.75,1.75)
HINFO = (7.25,8.25,8.75,0.75)
HSMALL = (7.25,3.5,4.5,4.5)
HSTATUS = (12,3.5,4,4.5)
HLOG = (7.25,0,8.75,3.25)

#Vertical orientation:
VRATIO = (9,16)
VINFO = (0,15.25,9,0.75)
VBIG = (0,8,7,7)
VNAV = (7.25,13.25,1.75,1.75)
VTORP = (7.25,11.5,1.75,1.75)
VPHASER = (7.25,9.75,1.75,1.75)
VREPAIR = (7.25,8,1.75,1.75)
VSMALL = (0,3.25,4.5,4.5)
VSTATUS = (4.75,3.25,4.25,4.5)
VLOG = (0,0,9,3)

SCREEN_TITLE = "Space Trek"


class TorpedoStatus(arcade.Sprite):
    def __init__(self, game, index, **kwargs):
        super().__init__(**kwargs)
        self.texture = game.missle_texture
        self.index = index
    def update(self,game):
        if game.ship.torpedoes > self.index:
            self.color = (255,255,255,255)
        else:
            self.color = (255,255,255,64)

class ShieldStatus(arcade.Sprite):
    def __init__(self, game, **kwargs):
        super().__init__(**kwargs)
        self.texture = game.shield_texture
    def update(self,game):
        if game.ship.shields == 0:
            self.color = (255,255,255,0)
        else:
            self.color = (255,255,255,(game.ship.shields/200+0.5)*255)

class Explosion(arcade.Sprite):
    def __init__(self, texture_list, center_x, center_y, scale=1.0):
        super().__init__(texture_list[0], scale=scale, center_x=center_x, center_y=center_y)
        self.textures = texture_list
        self.current_texture_index = 0
        self.animation_speed = 0.1

    def update_animation(self, delta_time: float = 1/60):
        self.current_texture_index += 1
        if self.current_texture_index >= len(self.textures):
            self.remove_from_sprite_lists()
        else:
            self.set_texture(self.current_texture_index)

class Object(arcade.Sprite):
    def __init__(self, type, rc, health, pctsize=0.8, **kwargs):
        super().__init__(**kwargs)
        self.type = type
        self.health = health
        self.shields = 0
        self.rc = rc
        self.pctsize = pctsize
        self.turning = False
        self.target_angle = 0
        self.current_turn_velocity = 0
        self.max_turn_velocity = 8
        self.turn_accel = 0.1
        self.moving = False
        self.target_rc = (0,0)
        self.current_velocity = 0
        self.max_velocity = 8
        self.accel = 0.5

class Ship(Object):
    def __init__(self, **kwargs):
        super().__init__(type="U", health=100, **kwargs)
        self.energy = MAX_ENERGY
        self.shields = 0
        self.health = [100,100,100]   # torpedoes, phasers, engines
        self.torpedoes = 10
        self.turn_accel = 0.5
        self.docking = False
        self.docked = False
        self.firing = None
        self.original_scale = 1

    def fire_to(self,game,tx,ty,firing):
        self.turning = True
        fr,fc = self.rc[0],self.rc[1]
        fxy = game.biggrid_xy[fr][fc]
        self.target_angle = math.degrees(math.atan2(fxy[1]-ty, tx-fxy[0]))
        self.firing = firing
        game.currently_firing = PHASER_DURATION
        game.enemy_turn += 1

    def move_to(self,game,tr,tc,docking):
        self.turning = True
        self.docked = False
        fr,fc = self.rc[0],self.rc[1]
        fxy = game.biggrid_xy[fr][fc]
        txy = game.biggrid_xy[tr][tc]
        self.target_angle = math.degrees(math.atan2(fxy[1]-txy[1], txy[0]-fxy[0]))
        self.moving = True
        self.target_rc = (tr,tc)
        self.docking = docking
        if not docking:
            game.enemy_turn += 1

    def update(self,game):
        if self.moving == False or self.turning == True:
            r,c = self.rc[0],self.rc[1]
            x,y = game.biggrid_xy[r][c][0],game.biggrid_xy[r][c][1]
            self.center_x = x
            self.center_y = y
        if self.turning == True:
            diff = (self.target_angle - self.angle + 180) % 360 - 180
            abs_diff = abs(diff)
            if abs_diff < abs(self.current_turn_velocity) or abs_diff < 0.1:
                self.angle = self.target_angle
                self.current_turn_velocity = 0
                self.turning = False
                return
            safe_speed = math.sqrt(2 * self.turn_accel * abs_diff)
            if diff > 0:
                if self.current_turn_velocity < safe_speed:
                    self.current_turn_velocity += self.turn_accel
                else:
                    self.current_turn_velocity -= self.turn_accel
            else:
                if self.current_turn_velocity > -safe_speed:
                    self.current_turn_velocity -= self.turn_accel
                else:
                    self.current_turn_velocity += self.turn_accel
            if (diff > 0 and self.current_turn_velocity < 0) or (diff < 0 and self.current_turn_velocity > 0):
                if abs_diff < 1:
                    self.angle = self.target_angle
                    self.current_turn_velocity = 0
                    self.turning = False
                    return
            if abs(self.current_turn_velocity) > self.max_turn_velocity:
                self.current_turn_velocity = (1 if self.current_turn_velocity > 0 else -1) * self.max_turn_velocity
            self.angle += self.current_turn_velocity
            return
        if self.moving == True:
            # set center_x and center_y based on location in big grid between current rc and target rc
            fr,fc = self.rc[0],self.rc[1]
            fx,fy = game.biggrid_xy[fr][fc][0],game.biggrid_xy[fr][fc][1]
            tr,tc = self.target_rc[0],self.target_rc[1]
            tx,ty = game.biggrid_xy[tr][tc][0],game.biggrid_xy[tr][tc][1]
            dx = tx - self.center_x
            dy = ty - self.center_y
            dist = math.sqrt(dx**2 + dy**2)
            if dist < abs(self.current_velocity) or dist < 0.5:
                self.center_x,self.center_y = tx,ty
                self.current_velocity = 0
                self.rc = self.target_rc
                self.moving = False
                return
            safe_speed = math.sqrt(2*self.accel*dist)
            if self.current_velocity < safe_speed:
                self.current_velocity += self.accel
            else:
                self.current_velocity -= self.accel
            if self.current_velocity > self.max_velocity:
                self.current_velocity = self.max_velocity
            self.center_x += (dx / dist) * self.current_velocity
            self.center_y += (dy / dist) * self.current_velocity
            return
        if self.firing == "T":
            r,c = self.rc[0],self.rc[1]
            x,y = game.biggrid_xy[r][c][0],game.biggrid_xy[r][c][1]
            d = (105-self.health[0])/100 * 15
            angle = self.angle + random.uniform(-d,d)
            torp = Torpedo(x,y,angle)
            torp.texture = game.torp_texture
            game.torp_sprites.append(torp)
            self.firing = None
        if self.firing == "P":
            game.add_phaser(self.rc, (self.center_x,self.center_y), self.angle, False)
            self.firing = None
        if self.docked and game.base_sprites:
            self.angle = self.angle + game.base_sprites[0].turn_speed % 360



class Star(Object):
    def __init__(self, **kwargs):
        super().__init__(type="S", health=99999999, **kwargs)
        self.turn_speed = 0

    def update(self,game):
        self.angle = self.angle + self.turn_speed % 360

class Base(Object):
    def __init__(self, **kwargs):
        super().__init__(type="B", health=1000, pctsize=0.9, **kwargs)
        self.turn_speed = 0

    def update(self,game):
        self.angle = self.angle + self.turn_speed % 360

class Enemy(Object):
    def __init__(self, **kwargs):
        super().__init__(type="E", health=100, **kwargs)
        self.last_turn = 0

    def update(self,game):
        fr,fc = self.rc[0],self.rc[1]
        tr,tc = game.ship.rc[0],game.ship.rc[1]
        fx,fy = game.biggrid_xy[fr][fc][0],game.biggrid_xy[fr][fc][1]
        tx,ty = game.biggrid_xy[tr][tc][0],game.biggrid_xy[tr][tc][1]
        self.target_angle = math.degrees(math.atan2(fy-ty, tx-fx))
        diff = (self.target_angle - self.angle + 180) % 360 - 180
        abs_diff = abs(diff)
        if abs_diff < abs(self.current_turn_velocity) or abs_diff < 0.1:
            self.angle = self.target_angle
            self.current_turn_velocity = 0
            self.turning = False
            return
        self.turning = True
        safe_speed = math.sqrt(2 * self.turn_accel * abs_diff)
        if diff > 0:
            if self.current_turn_velocity < safe_speed:
                self.current_turn_velocity += self.turn_accel
            else:
                self.current_turn_velocity -= self.turn_accel
        else:
            if self.current_turn_velocity > -safe_speed:
                self.current_turn_velocity -= self.turn_accel
            else:
                self.current_turn_velocity += self.turn_accel
        if (diff > 0 and self.current_turn_velocity < 0) or (diff < 0 and self.current_turn_velocity > 0):
            if abs_diff < 1:
                self.angle = self.target_angle
                self.current_turn_velocity = 0
                self.turning = False
                return
        if abs(self.current_turn_velocity) > self.max_turn_velocity:
            self.current_turn_velocity = (1 if self.current_turn_velocity > 0 else -1) * self.max_turn_velocity
        self.angle += self.current_turn_velocity


class Sector():
    def __init__(self, **kwargs):
        self.enemies=0
        self.bases=0
        self.stars=0
        self.explored=False
        self.rc=(0,0)
        self.grid={}

class Starfield:
    def __init__(self):
        self.sprite = arcade.SpriteSolidColor(2.5, 2.5, 0, 0, arcade.color.WHITE)
        self.sw = SCREEN_WIDTH
        self.sh = SCREEN_HEIGHT
        self.last_x = SCREEN_WIDTH/2
        self.last_y = SCREEN_HEIGHT/2
        self.reset()

    def reset(self):
        cx = SCREEN_WIDTH/2
        cy = SCREEN_HEIGHT/2
        self.x = random.uniform(-self.sw, self.sw)
        self.y = random.uniform(-self.sh, self.sh)
        self.z = random.uniform(0.1, 1.0)
        self.speed = random.uniform(0.005, 0.015)
        self.sprite.center_x = (self.x / self.z) + cx
        self.sprite.center_y = (self.y / self.z) + cy
        self.sprite.angle = math.degrees(math.atan2(self.sprite.center_y-cy, cx-self.sprite.center_x))


    def update_pos(self, warping):
        old_x = self.sprite.center_x
        old_y = self.sprite.center_y
        cx = SCREEN_WIDTH/2
        cy = SCREEN_HEIGHT/2
        actual_speed = self.speed + self.speed*warping/10
        self.z -= actual_speed
        if self.z <= 0:
            self.reset()
            self.z = 1.0
            reset = True
        else:
            reset = False
        self.sprite.center_x = (self.x / self.z) + cx
        self.sprite.center_y = (self.y / self.z) + cy
        self.sprite.scale = (1.0 - self.z) * 1.5
        self.sprite.alpha = int((1.0 - self.z) * 255)
        if warping and not reset:
            dist = math.sqrt((self.sprite.center_x-old_x)**2 + (self.sprite.center_y-old_y)**2)
            self.sprite.width += dist + dist*warping/100


class Torpedo(arcade.Sprite):
    def __init__(self, fx, fy, angle, **kwargs):
        super().__init__(**kwargs)
        self.scale = 0
        self.pctsize = 0.25
        self.center_x = fx
        self.center_y = fy
        self.fire_angle = angle
        self.velocity = 10
        self.angle_change = 0

    def update(self,game):
        self.angle_change = max(min(self.angle_change + random.uniform(-5,5),15),-15)
        self.angle = self.angle + self.angle_change % 360
        if self.fire_angle == None:
            return
        dx = math.cos(math.radians(self.fire_angle)) * self.velocity
        dy = math.sin(math.radians(self.fire_angle)) * self.velocity
        self.center_x += dx
        self.center_y -= dy
        if (self.center_x > game.big_xy[0]+game.big_wh[0]/2 or
            self.center_x < game.big_xy[0]-game.big_wh[0]/2 or
            self.center_y > game.big_xy[1]+game.big_wh[1]/2 or
            self.center_y < game.big_xy[1]-game.big_wh[1]/2):
            self.remove_from_sprite_lists()

class Phaser:
    def __init__(self, game, rc, xy, angle, enemy):
        self.rc = rc
        self.xy = xy
        self.angle = angle
        self.last_angle = angle
        self.enemy = enemy
        self.duration = 1
        self.first_fire = True
        if self.enemy:
            self.color = ENEMY_COLOR
        else:
            self.color = PHASER_COLOR

    def update(self,game):
        if self.rc not in game.sector.grid:
            self.duration = 0
            return
        if not self.enemy:
            if not game.firing_phasers and not self.first_fire:
                self.duration = 0
                return
            game.ship.energy -= 1
            if game.ship.energy == 0:
                self.duration = 0
                game.firing_phasers = False
                game.button = None
                game.message("Phaser banks depleted!",WARNING_MESSAGE_COLOR,True)
                return
        fx = self.xy[0]
        fy = self.xy[1]
        if self.enemy:
            h = game.sector.grid[self.rc].health
        else:
            h = game.ship.health[1]
        d = (105-h)/100 * 4
        dm = d*15

        offset = self.last_angle - self.angle
        offset_ratio = offset / dm
        centering = offset_ratio * d
        jitter = random.uniform(-d, d) - centering
        angle = self.last_angle + jitter
        dml = self.angle - dm
        dmh = self.angle + dm
        angle = max(dml, min(dmh, angle))
        self.last_angle = angle

        enemy = self.enemy
        color = self.color
        dist = SCREEN_WIDTH+SCREEN_HEIGHT
        dx,dy = math.cos(math.radians(angle))*dist,0-math.sin(math.radians(angle))*dist
        tx,ty = fx+dx,fy+dy
        line = arcade.SpriteSolidColor(int(dist), 2, arcade.color.WHITE)
        line.center_x = (fx+tx)/2
        line.center_y = (fy+ty)/2
        line.angle = angle

        closest = None
        if enemy:
            hit_list = arcade.check_for_collision_with_lists(line, [game.ship_sprites, game.star_sprites, game.base_sprites])
        else:
            hit_list = arcade.check_for_collision_with_lists(line, [game.enemy_sprites, game.star_sprites, game.base_sprites])
        if hit_list:
            for sprite in hit_list:
                temp = math.sqrt(abs(fx-sprite.center_x)**2 + abs(fy-sprite.center_y)**2)
                if temp < dist:
                    dist = temp
                    closest = sprite
        if closest:
            dx,dy = math.cos(math.radians(angle)),0-math.sin(math.radians(angle))
            rx,ry = closest.center_x - fx, closest.center_y - fy
            dist = (rx * dx) + (ry * dy)
            tx = fx + dist * dx
            ty = fy + dist * dy
            if enemy and closest.type == "U":
                game.damage_ship(random.uniform(ENEMY_DAMAGE_LOW,ENEMY_DAMAGE_HIGH))              # Phaser damage per frame
            if not enemy and closest.type == "E":
                game.damage_enemy(closest,random.uniform(PHASER_DAMAGE_LOW,PHASER_DAMAGE_HIGH))   # Phaser damage per frame
            game.explosion(tx+random.uniform(-game.biggrid_wh[0]*.25,game.biggrid_wh[0]*.25),ty+random.uniform(-game.biggrid_wh[1]*.25,game.biggrid_wh[1]*.25),0.15)
        else:
            left = game.big_xy[0]-game.big_wh[0]/2
            right = game.big_xy[0]+game.big_wh[0]/2
            bottom = game.big_xy[1]-game.big_wh[1]/2
            top = game.big_xy[1]+game.big_wh[1]/2
            dx,dy = math.cos(math.radians(angle)),0-math.sin(math.radians(angle))
            t = []
            if abs(dx) > 1e-9:
                t.append((left - fx)/dx)
                t.append((right - fx)/dx)
            if abs(dy) > 1e-9:
                t.append((bottom - fy)/dy)
                t.append((top - fy)/dy)
            t3 = [t2 for t2 in t if t2 > 0]
            dist = min(t3)
            tx = fx + dist * dx
            ty = fy + dist * dy
        size = game.smallgrid_wh[0]*.05
        game.draw_phaser(game.phaser_shapes,fx,fy,tx,ty,size,color)
        self.duration += 1
        if enemy:
            if self.duration > PHASER_DURATION:
                self.duration = 0
        else:
            if self.duration > PHASER_DURATION:
                self.first_fire = False
            if self.duration > PHASER_DURATION*1.25:
                self.duration = 1
                game.enemy_turn += 1

class MyGame(arcade.Window):
    def __init__(self):
        print("init")
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE,resizable=True)
        self.camera = arcade.Camera2D(LBWH(0,0,1920,1080),(0.0,0.0),(0,1),1.0,LBWH(0,0,SCREEN_WIDTH,SCREEN_HEIGHT))
        arcade.set_background_color(arcade.color.BLACK)
        self.frame = 0
        self.sectors = 6
        self.cells = 8
        self.log_scroll = 0
        self.enemies = round(self.sectors*self.sectors*1)
        self.bases = round(self.sectors*self.sectors*.25)
        self.stars = round(self.sectors*self.sectors*4)
        self.define_screen(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.days = MAX_DAYS
        self.warping = MAX_WARP/2+1
        self.warp_sector = (random.randrange(self.sectors),random.randrange(self.sectors))
        self.button = None
        self.fire_target = None
        self.last_phaser = 0
        self.phasers = {}
        self.firing_phasers = False
        self.enemy_turn = 0
        self.currently_firing = 0
        self.base = None
        self.log = []
        self.messages = deque([])
        self.message_frames = 0
        self.message("Captain on the bridge!",INFO_MESSSAGE_COLOR,True)
        self.scrollbar = None
        self.drag_remainder = None
        self.last_damage_frame = 0
        self.last_damage_type = 0

    def on_resize(self, width, height):
        super().on_resize(width, height)
        l = 0
        b = 0
        w = width
        h = height
        if w/h > SCREEN_ASPECT:
            w = h*SCREEN_ASPECT
        else:
            h = w/SCREEN_ASPECT
        l = (width-w)/2
        b = (height-h)/2
        self.camera.viewport = LBWH(l,b,w,h)

    def define_screen(self, width, height):
        # _lb is x,y left bottom
        # _wh is width, height
        # _xy is x,y center
        if width > height:
            RATIO = HRATIO
            BIG = HBIG
            TORP = HTORP
            PHASER = HPHASER
            SHIELD = HNAV
            REPAIR = HREPAIR
            INFO = HINFO
            SMALL = HSMALL
            STATUS = HSTATUS
            LOG = HLOG
            VERTICAL = False
        else:
            RATIO = VRATIO
            BIG = VBIG
            TORP = VTORP
            PHASER = VPHASER
            SHIELD = VNAV
            REPAIR = VREPAIR
            INFO = VINFO
            SMALL = VSMALL
            STATUS = VSTATUS
            LOG = VLOG
            VERTICAL = True
        ratio = RATIO[0]/RATIO[1]
        ratio_difference = width/height - ratio
        if ratio_difference >= 0:
            content_w = height * ratio
            content_h = height
        elif ratio_difference < 0:
            content_w = width
            content_h = width / ratio
        extra_x = (width - content_w)/2
        extra_y = (height - content_h)/2
        border = content_w * .025
        content_w -= border
        content_h -= border
        extra_x += border/2
        extra_y += border/2

        self.big_wh = (content_w*BIG[2]/RATIO[0],content_h*BIG[3]/RATIO[1])
        self.big_lb = (content_w*BIG[0]/RATIO[0]+extra_x,content_h*BIG[1]/RATIO[1]+extra_y)
        self.big_xy = (self.big_lb[0]+self.big_wh[0]/2,self.big_lb[1]+self.big_wh[1]/2)

        self.biggrid_wh = (self.big_wh[0]/self.cells,self.big_wh[1]/self.cells)
        self.biggrid_lb = [
            [(self.big_lb[0] + c*self.biggrid_wh[0],self.big_lb[1] + r*self.biggrid_wh[1]) for r in range(self.cells)]
            for c in range(self.cells)
        ]
        self.biggrid_xy = [
            [(self.big_lb[0] + c*self.biggrid_wh[0] + self.biggrid_wh[0]/2,self.big_lb[1] + r*self.biggrid_wh[1] + self.biggrid_wh[1]/2) for r in range(self.cells)]
            for c in range(self.cells)
        ]

        self.torp_wh = (content_w*TORP[2]/RATIO[0],content_h*TORP[3]/RATIO[1])
        self.torp_lb = (content_w*TORP[0]/RATIO[0]+extra_x,content_h*TORP[1]/RATIO[1]+extra_y)
        self.torp_xy = (self.torp_lb[0]+self.torp_wh[0]/2,self.torp_lb[1]+self.torp_wh[1]/2)

        self.phaser_wh = (content_w*PHASER[2]/RATIO[0],content_h*PHASER[3]/RATIO[1])
        self.phaser_lb = (content_w*PHASER[0]/RATIO[0]+extra_x,content_h*PHASER[1]/RATIO[1]+extra_y)
        self.phaser_xy = (self.phaser_lb[0]+self.phaser_wh[0]/2,self.phaser_lb[1]+self.phaser_wh[1]/2)

        self.nav_wh = (content_w*SHIELD[2]/RATIO[0],content_h*SHIELD[3]/RATIO[1])
        self.nav_lb = (content_w*SHIELD[0]/RATIO[0]+extra_x,content_h*SHIELD[1]/RATIO[1]+extra_y)
        self.nav_xy = (self.nav_lb[0]+self.nav_wh[0]/2,self.nav_lb[1]+self.nav_wh[1]/2)

        self.repair_wh = (content_w*REPAIR[2]/RATIO[0],content_h*REPAIR[3]/RATIO[1])
        self.repair_lb = (content_w*REPAIR[0]/RATIO[0]+extra_x,content_h*REPAIR[1]/RATIO[1]+extra_y)
        self.repair_xy = (self.repair_lb[0]+self.repair_wh[0]/2,self.repair_lb[1]+self.repair_wh[1]/2)

        self.info_wh = (content_w*INFO[2]/RATIO[0],content_h*INFO[3]/RATIO[1])
        self.info_lb = (content_w*INFO[0]/RATIO[0]+extra_x,content_h*INFO[1]/RATIO[1]+extra_y)
        self.info_xy = (self.info_lb[0]+self.info_wh[0]/2,self.info_lb[1]+self.info_wh[1]/2)

        self.small_wh = (content_w*SMALL[2]/RATIO[0],content_h*SMALL[3]/RATIO[1])
        self.small_lb = (content_w*SMALL[0]/RATIO[0]+extra_x,content_h*SMALL[1]/RATIO[1]+extra_y)
        self.small_xy = (self.small_lb[0]+self.small_wh[0]/2,self.small_lb[1]+self.small_wh[1]/2)

        self.smallgrid_wh = (self.small_wh[0]/self.sectors,self.small_wh[1]/self.sectors)
        self.smallgrid_lb = [
            [(self.small_lb[0] + c*self.smallgrid_wh[0],self.small_lb[1] + r*self.smallgrid_wh[1]) for r in range(self.sectors)]
            for c in range(self.sectors)
        ]
        self.smallgrid_xy = [
            [(self.small_lb[0] + c*self.smallgrid_wh[0] + self.smallgrid_wh[0]/2,self.small_lb[1] + r*self.smallgrid_wh[1] + self.smallgrid_wh[1]/2) for r in range(self.sectors)]
            for c in range(self.sectors)
        ]

        self.status_wh = (content_w*STATUS[2]/RATIO[0],content_h*STATUS[3]/RATIO[1])
        self.status_lb = (content_w*STATUS[0]/RATIO[0]+extra_x,content_h*STATUS[1]/RATIO[1]+extra_y)
        self.status_xy = (self.status_lb[0]+self.status_wh[0]/2,self.status_lb[1]+self.status_wh[1]/2)

        self.log_wh = (content_w*LOG[2]/RATIO[0],content_h*LOG[3]/RATIO[1])
        self.log_lb = (content_w*LOG[0]/RATIO[0]+extra_x,content_h*LOG[1]/RATIO[1]+extra_y)
        self.log_xy = (self.log_lb[0]+self.log_wh[0]/2,self.log_lb[1]+self.log_wh[1]/2)

        # Define major gridlines shape list
        self.gridlines = shape_list.ShapeElementList()

        self.gridlines.append(shape_list.create_rectangle_filled(*self.big_xy,*self.big_wh,BIG_FILLED))
        self.gridlines.append(shape_list.create_rectangle_filled(*self.small_xy,*self.small_wh,SMALL_FILLED))
        self.gridlines.append(shape_list.create_rectangle_filled(*self.info_xy,*self.info_wh,INFO_FILLED))
        self.gridlines.append(shape_list.create_rectangle_filled(*self.status_xy,*self.status_wh,STATUS_FILLED))
        self.gridlines.append(shape_list.create_rectangle_filled(*self.log_xy,*self.log_wh,LOG_FILLED))
        self.gridlines.append(shape_list.create_rectangle_filled(*self.torp_xy,*self.torp_wh,BUTTON_FILLED))
        self.gridlines.append(shape_list.create_rectangle_filled(*self.phaser_xy,*self.phaser_wh,BUTTON_FILLED))
        self.gridlines.append(shape_list.create_rectangle_filled(*self.nav_xy,*self.nav_wh,BUTTON_FILLED))
        self.gridlines.append(shape_list.create_rectangle_filled(*self.repair_xy,*self.repair_wh,BUTTON_FILLED))

        self.gridlines.append(shape_list.create_rectangle_outline(*self.big_xy,*self.big_wh,BIG_OUTLINE,border_width=GRIDLINE_WIDTH))
        self.gridlines.append(shape_list.create_rectangle_outline(*self.small_xy,*self.small_wh,SMALL_OUTLINE,border_width=GRIDLINE_WIDTH))
        self.gridlines.append(shape_list.create_rectangle_outline(*self.info_xy,*self.info_wh,INFO_OUTLINE,border_width=GRIDLINE_WIDTH))
        self.gridlines.append(shape_list.create_rectangle_outline(*self.status_xy,*self.status_wh,STATUS_OUTLINE,border_width=GRIDLINE_WIDTH))
        self.gridlines.append(shape_list.create_rectangle_outline(*self.log_xy,*self.log_wh,LOG_OUTLINE,border_width=GRIDLINE_WIDTH))
        self.gridlines.append(shape_list.create_rectangle_outline(*self.torp_xy,*self.torp_wh,BUTTON_OUTLINE,border_width=GRIDLINE_WIDTH))
        self.gridlines.append(shape_list.create_rectangle_outline(*self.phaser_xy,*self.phaser_wh,BUTTON_OUTLINE,border_width=GRIDLINE_WIDTH))
        self.gridlines.append(shape_list.create_rectangle_outline(*self.nav_xy,*self.nav_wh,BUTTON_OUTLINE,border_width=GRIDLINE_WIDTH))
        self.gridlines.append(shape_list.create_rectangle_outline(*self.repair_xy,*self.repair_wh,BUTTON_OUTLINE,border_width=GRIDLINE_WIDTH))

        # Define navigation area shape list
        self.navareas = shape_list.ShapeElementList()

        # Define minor gridlines shape list
        self.subgrid = shape_list.ShapeElementList()
        for row in self.biggrid_xy:
            for xy in row:
                self.subgrid.append(shape_list.create_rectangle_outline(*xy,*self.biggrid_wh,BIG_OUTLINE,border_width=SUBGRID_WIDTH))
        for row in self.smallgrid_xy:
            for xy in row:
                self.subgrid.append(shape_list.create_rectangle_outline(*xy,*self.smallgrid_wh,SMALL_OUTLINE,border_width=SUBGRID_WIDTH))

    def setup(self):
        print("setup")
        # Load textures
        self.enemy_texture = arcade.load_texture("data/enemy.png")
        self.ship_texture = arcade.load_texture("data/ship.png")
        self.shield_texture = arcade.load_texture("data/ship_shield.png")
        self.base_texture = arcade.load_texture("data/base.png")
        self.star_texture = arcade.load_texture("data/star.png")
        self.torp_texture = arcade.load_texture("data/torpedo.png")
        self.missle_texture = arcade.load_texture("data/missle.png")
        self.nav_texture = arcade.load_texture("data/nav.png")
        self.repair_texture = arcade.load_texture("data/repair.png")
        self.explosion_textures = arcade.load_spritesheet("data/explosion.png").get_texture_grid(size=(400,400), columns=5, count=45)

        # Define starfield objects
        self.starfield = []
        self.starfield_sprites = arcade.SpriteList()
        for _ in range(500):
            new_star = Starfield()
            self.starfield.append(new_star)
            self.starfield_sprites.append(new_star.sprite)

        # Define dynamic sprite and shape lists
        self.enemy_sprites = arcade.SpriteList(use_spatial_hash=True)
        self.star_sprites = arcade.SpriteList(use_spatial_hash=True)
        self.base_sprites = arcade.SpriteList(use_spatial_hash=True)
        self.torp_sprites = arcade.SpriteList(use_spatial_hash=True)
        self.phaser_shapes = shape_list.ShapeElementList()
        self.build_universe()
        self.ship_sprites = arcade.SpriteList(use_spatial_hash=True)
        self.ship_sprites.append(self.ship_shield)
        self.ship_sprites.append(self.ship)
        self.ui_sprites = arcade.SpriteList()
        self.ui_shapes = shape_list.ShapeElementList()
        self.explosion_sprites = arcade.SpriteList()

        self.debug_sprites = arcade.SpriteList()
        self.debug_shapes = shape_list.ShapeElementList()

        # Build UI sprites
        # Buttons
        img = arcade.Sprite(self.missle_texture)
        img.center_x = self.torp_xy[0]
        img.center_y = self.torp_xy[1]
        img.scale = self.torp_wh[0]/400*0.8
        img.update = lambda x: None
        self.ui_sprites.append(img)
        x,y = self.phaser_xy[0],self.phaser_xy[1]
        w,h = self.phaser_wh[0],self.phaser_wh[1]
        self.draw_phaser(self.ui_shapes,x+w/3,y-h/3,x-w/3,y+h/3,self.phaser_wh[0]*.04,PHASER_COLOR)
        img = arcade.Sprite(self.nav_texture)
        img.center_x = self.nav_xy[0]
        img.center_y = self.nav_xy[1]
        img.scale = self.nav_wh[0]/400*0.8
        img.update = lambda x: None
        self.ui_sprites.append(img)
        img = arcade.Sprite(self.repair_texture)
        img.center_x = self.repair_xy[0]
        img.center_y = self.repair_xy[1]
        img.scale = self.repair_wh[0]/400*0.8
        img.update = lambda x: None
        self.ui_sprites.append(img)

        # Status Area
        # Torpedo compliement
        w = self.status_wh[0]/11
        for i in range(10):
            img = TorpedoStatus(self,i)
            img.center_x = self.status_lb[0]+w*(i+1)
            img.center_y = self.status_lb[1]+self.status_wh[1]*.825
            img.scale = self.status_wh[0]/400*0.1*0.9
            self.ui_sprites.append(img)

        self.phaser_status_lb = (self.status_lb[0]+self.status_wh[0]*.05,self.status_lb[1]+self.status_wh[1]*.575)
        self.phaser_status_wh = (self.status_wh[0]*.9,self.status_wh[0]*.25*.25)

        # Ship Status
        img = ShieldStatus(self)
        img.center_x = self.status_lb[0]+self.status_wh[0]*.15
        img.center_y = self.status_lb[1]+self.status_wh[1]*.2
        img.scale = self.status_wh[0]/400*0.4*0.9
        img.angle = 270
        self.ui_sprites.append(img)
        img = arcade.Sprite(self.ship_texture)
        img.center_x = self.status_lb[0]+self.status_wh[0]*.15
        img.center_y = self.status_lb[1]+self.status_wh[1]*.2
        img.scale = self.status_wh[0]/400*0.4*0.9
        img.update = lambda x: None
        img.angle = 270
        self.ui_sprites.append(img)

        # Define UI Text Areas
        self.ui_text = Batch()
        x = self.info_xy[0]
        y = self.info_xy[1]
        s = self.info_wh[1]*.5
        self.info_message = arcade.Text("",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="center",anchor_y="center")
        x = self.log_xy[0]-self.log_wh[0]/2
        o = self.log_wh[1]/7
        y = self.log_xy[1]+o*3
        s = self.log_wh[1]/6*.5
        self.log_height = s
        self.log_stardate = [arcade.Text("",x+self.log_wh[0]*.01,y-(yo*o),arcade.color.LIGHT_GRAY,s,batch=self.ui_text,anchor_x="left",anchor_y="center") for yo in range(7)]
        self.log_message = [arcade.Text("",x+self.log_wh[0]/5,y-(yo*o),arcade.color.WHITE,s,batch=self.ui_text,anchor_x="left",anchor_y="center") for yo in range(7)]

        # Torpedoes
        x = self.status_lb[0]+self.status_wh[0]*.05
        y = self.status_lb[1]+self.status_wh[1]*.925
        s = self.status_wh[0]*0.25*0.25
        self.torp_text1 = arcade.Text("Torpedo Health",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="left",anchor_y="center")
        x = self.status_lb[0]+self.status_wh[0]*.95
        y = self.status_lb[1]+self.status_wh[1]*.925
        s = self.status_wh[0]*0.25*0.25
        self.torp_text2 = arcade.Text("",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="right",anchor_y="center")

        # Phasers
        x = self.status_lb[0]+self.status_wh[0]*.05
        y = self.status_lb[1]+self.status_wh[1]*.70
        s = self.status_wh[0]*0.25*0.25
        self.phaser_text1 = arcade.Text("Phaser Health",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="left",anchor_y="center")
        x = self.status_lb[0]+self.status_wh[0]*.95
        y = self.status_lb[1]+self.status_wh[1]*.70
        s = self.status_wh[0]*0.25*0.25
        self.phaser_text2 = arcade.Text("",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="right",anchor_y="center")

        # Engines
        x = self.status_lb[0]+self.status_wh[0]*.05
        y = self.status_lb[1]+self.status_wh[1]*.475
        s = self.status_wh[0]*0.25*0.25
        self.engine_text1 = arcade.Text("Warp Core Health",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="left",anchor_y="center")
        x = self.status_lb[0]+self.status_wh[0]*.95
        y = self.status_lb[1]+self.status_wh[1]*.475
        s = self.status_wh[0]*0.25*0.25
        self.engine_text2 = arcade.Text("",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="right",anchor_y="center")

        # Shields
        x = self.status_lb[0]+self.status_wh[0]*.3
        y = self.status_lb[1]+self.status_wh[1]*.325
        s = self.status_wh[0]*0.25*0.25
        self.shield_text1 = arcade.Text("Sheilds",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="left",anchor_y="center")
        x = self.status_lb[0]+self.status_wh[0]*.95
        y = self.status_lb[1]+self.status_wh[1]*.325
        s = self.status_wh[0]*0.25*0.25
        self.shield_text2 = arcade.Text("",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="right",anchor_y="center")

        # Enemies
        x = self.status_lb[0]+self.status_wh[0]*.3
        y = self.status_lb[1]+self.status_wh[1]*.2
        s = self.status_wh[0]*0.25*0.25
        self.enemies_text1 = arcade.Text("Enemies",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="left",anchor_y="center")
        x = self.status_lb[0]+self.status_wh[0]*.95
        y = self.status_lb[1]+self.status_wh[1]*.2
        s = self.status_wh[0]*0.25*0.25
        self.enemies_text2 = arcade.Text("",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="right",anchor_y="center")

        # Days
        x = self.status_lb[0]+self.status_wh[0]*.3
        y = self.status_lb[1]+self.status_wh[1]*.075
        s = self.status_wh[0]*0.25*0.25
        self.days_text1 = arcade.Text("Days Left",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="left",anchor_y="center")
        x = self.status_lb[0]+self.status_wh[0]*.95
        y = self.status_lb[1]+self.status_wh[1]*.075
        s = self.status_wh[0]*0.25*0.25
        self.days_text2 = arcade.Text("",x,y,arcade.color.WHITE,s,batch=self.ui_text,anchor_x="right",anchor_y="center")


        self.change_sector(*self.warp_sector,False)

    def add_phaser(self,rc,xy,angle,enemy):
        self.last_phaser += 1
        phaser = Phaser(self,rc,xy,angle,enemy)
        self.phasers[self.last_phaser] = phaser

    def draw_phaser(self,list,fx,fy,tx,ty,size,color):
        list.append(shape_list.create_lines_with_colors([(fx,fy),(tx,ty)],[(*color[:3],0),color],line_width=size))
        list.append(shape_list.create_ellipse_filled(tx,ty,size,size,color))

    def change_sector(self,r,c,cost):
        if cost:
            delay = max(1,round(math.sqrt((self.sector.rc[0]-r)**2 + (self.sector.rc[1]-c)**2)))
            d = (100-self.ship.health[2])/100
            delay = round(delay + d*2*delay)
            if delay == 1:
                days = str(delay) + " day"
            else:
                days = str(delay) + " days"
            self.days -= delay
            self.message(f"Warping to sector ({r+1},{self.sectors-c}) took "+days,INFO_MESSSAGE_COLOR,True)
        else:
            self.message(f"Warped into sector ({r+1},{self.sectors-c})",INFO_MESSSAGE_COLOR,True)
        if self.ship.docked:
            self.sector.grid[(self.ship.rc)] = self.base
        self.ship.docked = False
        self.enemy_sprites.clear()
        self.star_sprites.clear()
        self.base_sprites.clear()
        self.torp_sprites.clear()
        self.sector = self.universe[(r,c)]
        self.add_ship(self.sector)
        for sr in range(r-1,r+2):
            for sc in range(c-1,c+2):
                if 0 <= sr < self.sectors and 0 <= sc < self.sectors:
                    self.universe[(sr,sc)].explored = True
        grid = self.sector.grid
        for object in grid.values():
            match object.type:
                case "E":
                    self.enemy_sprites.append(object)
                    object.last_turn = self.enemy_turn
                case "S":
                    self.star_sprites.append(object)
                case "B":
                    self.base_sprites.append(object)
        self.shields_up()

    def shields_up(self):
        self.ship.shields = 100
        return
        amt = 100-self.ship.shields
        if self.ship.energy < amt:
            self.ship.shilelds += self.ship.energy
            self.ship.energy = 0
        else:
            self.ship.shields = 100
            self.ship.energy -= amt

    def shields_down(self):
        self.ship.energy += self.ship.shields
        self.ship.shields = 0

    def message(self,message,color,save):
        self.messages.append([message,color])
        if save:
            self.log.append([datetime.now(),message,color])
            if self.log_scroll > 0:
                self.log_scroll += 1

    def build_universe(self):
        self.universe = {}
        for r in range(self.sectors):
            for c in range(self.sectors):
                sector = Sector()
                sector.rc = (r,c)
                self.universe[(r,c)] = sector

        for _ in range(self.enemies):
            while True:
                sector = self.universe[random.randrange(self.sectors),random.randrange(self.sectors)]
                if sector.enemies < 3:
                    self.add_enemy(sector)
                    break
        for _ in range(self.bases):
            while True:
                sector = self.universe[random.randrange(self.sectors),random.randrange(self.sectors)]
                if sector.bases < 1:
                    self.add_base(sector)
                    break
        for _ in range(self.stars):
            while True:
                sector = self.universe[random.randrange(self.sectors),random.randrange(self.sectors)]
                if sector.stars < 5:
                    self.add_star(sector)
                    break
        self.ship_shield = Ship(rc=(0,0))
        self.ship_shield.texture = self.shield_texture
        self.ship = Ship(rc=(0,0))
        self.ship.texture = self.ship_texture
        self.ship.scale = self.biggrid_wh[0]*self.ship.pctsize/400
        self.ship.original_scale = self.ship.scale

    def add_enemy(self,sector):
        sector.enemies += 1
        grid = sector.grid
        while True:
            rc = random.randrange(self.cells),random.randrange(self.cells)
            if rc not in grid:
                enemy = Enemy(rc=rc)
                enemy.texture = self.enemy_texture
                grid[rc] = enemy
                break

    def add_base(self,sector):
        sector.bases += 1
        grid = sector.grid
        while True:
            rc = random.randrange(self.cells),random.randrange(self.cells)
            if rc not in grid:
                base = Base(rc=rc)
                base.texture = self.base_texture
                turn_speed = random.uniform(-0.25,-0.1)
                if random.random() < 0.5:
                    turn_speed *= -1
                base.turn_speed = turn_speed
                grid[rc] = base
                break

    def add_star(self,sector):
        sector.stars += 1
        grid = sector.grid
        while True:
            rc = random.randrange(self.cells),random.randrange(self.cells)
            if rc not in grid:
                star = Star(rc=rc)
                star.pctsize = random.randrange(50,95)/100
                star.texture = self.star_texture
                turn_speed = random.uniform(-0.25,-0.1)
                if random.random() < 0.5:
                    turn_speed *= -1
                star.turn_speed = turn_speed
                grid[rc] = star
                break

    def add_ship(self,sector):
        grid = sector.grid
        while True:
            rc = random.randrange(self.cells),random.randrange(self.cells)
            if rc not in grid:
                self.ship.rc = rc
                grid[rc] = self.ship
                break


    def on_update(self, delta_time):
#        print(datetime.now())
        self.frame += 1
        if self.warping > 0:
            if self.warping == MAX_WARP/2:
                self.change_sector(*self.warp_sector,True)
            if self.warping < MAX_WARP/2:
                pct = ((MAX_WARP/2)-self.warping)/(MAX_WARP/2)
            else:
                pct = (self.warping-(MAX_WARP/2))/(MAX_WARP/2)
            self.ship.scale = (self.ship.original_scale[0]*pct,self.ship.original_scale[1]*pct)
            self.warping += 1
            if self.warping > MAX_WARP:
                self.warping = 0
                self.ship.scale = self.ship.original_scale
        if self.message_frames > 0:
            self.message_frames -= 1
        else:
            if self.messages:
                msg = self.messages.popleft()
                self.info_message.text = msg[0]
                self.info_message.color = msg[1]
                self.message_frames = MESSAGE_DELAY
            else:
                self.info_message.text = "Space Trek"
                self.info_message.color = INFO_MESSSAGE_COLOR

        # Captain's Log
        log_lines = len(self.log)
        log_size = len(self.log_message)
        skip = log_lines-log_size
        if skip > 0:
            skip = max(0,skip - self.log_scroll)
            # draw scroll bar
            w = self.log_wh[0]*0.0125
            h = self.log_wh[1]*0.95
            x = self.log_lb[0] + self.log_wh[0] - self.log_wh[1]*.05 - w
            y = self.log_lb[1] + self.log_wh[1]*0.025
            th = h * (log_size / log_lines)
            sr = self.log_scroll / (log_lines - log_size)
            ts = h - th
            h = th
            y = y + sr*ts
            self.scrollbar = (x,y,w,h)
        else:
            skip = 0
            self.scrollbar = None
        for i in range(min(len(self.log_message),len(self.log))):
            l = i + skip
            self.log_stardate[i].text = self.log[l][0].strftime("%H%M.%S%f")[:9]
            self.log_message[i].text = self.log[l][1]
            self.log_message[i].color = self.log[l][2]
        if self.ship.health[0] == 0 and self.button == "T": self.button = None
        if self.ship.health[1] == 0 and self.button == "P": self.button = None

        self.phaser_shapes.clear()
        self.update_starfield()
        if self.currently_firing > 0:
            self.currently_firing -= 1
        for object in self.enemy_sprites:
            xy = self.biggrid_xy[object.rc[0]][object.rc[1]]
            object.center_x = xy[0]
            object.center_y = xy[1]
            object.update(self)
            object.scale = self.biggrid_wh[0]*object.pctsize/400
            if object.last_turn < self.enemy_turn and object.turning == False and self.ship.moving == False:
                self.enemy_fire(object)
        for object in self.star_sprites:
            xy = self.biggrid_xy[object.rc[0]][object.rc[1]]
            object.center_x = xy[0]
            object.center_y = xy[1]
            object.update(self)
            object.scale = self.biggrid_wh[0]*object.pctsize/400
        for object in self.base_sprites:
            xy = self.biggrid_xy[object.rc[0]][object.rc[1]]
            object.center_x = xy[0]
            object.center_y = xy[1]
            object.update(self)
            object.scale = self.biggrid_wh[0]*object.pctsize/400
        for object in self.torp_sprites:
            object.update(self)
            object.scale = self.biggrid_wh[0]*object.pctsize/400
            hit_list = arcade.check_for_collision_with_lists(object, [self.star_sprites, self.base_sprites, self.enemy_sprites])
            if hit_list:
                hit=hit_list[0]
                self.explosion(object.center_x,object.center_y,0.5)
                object.remove_from_sprite_lists()
                match hit.type:
                    case "E":
                        self.damage_enemy(hit,random.uniform(TORPEDO_DAMAGE_LOW,TORPEDO_DAMAGE_HIGH))    # Torpedo damage to enemy (one time)
        for object in self.phasers.values():
            object.update(self)
        self.phasers = {
            key: object for key, object in self.phasers.items()
            if object.duration > 0
        }
        self.explosion_sprites.update_animation(delta_time)

        xy = self.biggrid_xy[self.ship.rc[0]][self.ship.rc[1]]
        self.ship.update(self)
        self.ship_shield.center_x = self.ship.center_x
        self.ship_shield.center_y = self.ship.center_y
        self.ship_shield.angle = self.ship.angle
        if self.ship.shields > 0:
            self.ship_shield.scale = self.ship.scale
        else:
            self.ship_shield.scale = 0
        self.update_navareas()
        if self.ship.moving == False and self.ship.docking == True:
            self.ship.docked = True
            self.ship.docking = False
            delay = self.repairs(True)
            match delay:
                case 0:
                    msg = "Docked - Repairs took under a day"
                case 1:
                    msg = "Docked - Repairs took 1 day"
                case _:
                    msg = f"Docked - Repairs took {delay} days"
            self.message(msg,INFO_MESSSAGE_COLOR,True)
        hit_list = arcade.check_for_collision_with_lists(self.ship, [self.star_sprites, self.base_sprites, self.enemy_sprites])
        if hit_list:
            hit=hit_list[0]
            match hit.type:
                case "E":
                    self.explosion(hit.center_x+random.uniform(-self.biggrid_wh[0]*.25,self.biggrid_wh[0]*.25),hit.center_y+random.uniform(-self.biggrid_wh[1]*.25,self.biggrid_wh[1]*.25),0.2)
                    self.damage_enemy(hit,random.randrange(2,5))       # Collision damage to enemy by ship (per frame)
                    self.explosion(self.ship.center_x+random.uniform(-self.biggrid_wh[0]*.25,self.biggrid_wh[0]*.25),self.ship.center_y+random.uniform(-self.biggrid_wh[1]*.25,self.biggrid_wh[1]*.25),0.2)
                    self.damage_ship(random.randrange(2,5))            # Collision damage to ship by enemy (per frame)
                case "S":
                    self.explosion(self.ship.center_x+random.uniform(-self.biggrid_wh[0]*.25,self.biggrid_wh[0]*.25),self.ship.center_y+random.uniform(-self.biggrid_wh[1]*.25,self.biggrid_wh[1]*.25),0.2)
                    self.damage_ship(random.randrange(2,5))            # Collision damage to ship by star (per frame)
        for object in self.ui_sprites:
            object.update(self)
        

    def repairs(self,docked):
        missing_health = (300-(sum(self.ship.health)))/100
        missing_shields = (100-self.ship.shields)/100
        if docked:
            missing_energy = (MAX_ENERGY-self.ship.energy)/MAX_ENERGY
            missing_torps = 10-self.ship.torpedoes
            delay = (missing_health+missing_shields+missing_energy+missing_torps)/6*MAX_REPAIR_DELAY/2
            self.ship.torpedoes = 10
            self.ship.energy = MAX_ENERGY
        else:
            delay = (missing_health+missing_shields)/4*MAX_REPAIR_DELAY
        self.ship.health = [100,100,100]
        self.ship.shields = 100
        delay = round(delay)
        self.days -= delay
        return delay


    def update_starfield(self):
        cx,cy = SCREEN_WIDTH/2, SCREEN_HEIGHT/2
        for star in self.starfield:
            old_x = (star.x / star.z) + cx
            old_y = (star.y / star.z) + cy
            star.update_pos(self.warping)
            new_x = (star.x / star.z) + cx
            new_y = (star.y / star.z) + cy

    def enemy_fire(self,enemy):
        enemy.last_turn += 1
        fxy = (enemy.center_x,enemy.center_y)
        rc = self.ship.rc
        txy = self.biggrid_xy[rc[0]][rc[1]]
        angle = math.degrees(math.atan2(fxy[1]-txy[1], txy[0]-fxy[0]))
        self.add_phaser(enemy.rc,fxy,angle,True)

    def damage_enemy(self,enemy,damage):
#        print("damage_enemy")
        enemy.health -= damage
        if enemy.health <= 0:
            self.explosion(enemy.center_x,enemy.center_y,1)
            enemy.remove_from_sprite_lists()
            temp = self.sector.grid.pop(enemy.rc)
            self.message("Enemy destroyed!",GOOD_MESSAGE_COLOR,True)
            self.sector.enemies -= 1
            self.enemies -= 1

    def damage_ship(self,damage):
        sd = damage
        hd = damage*0.1
        if self.ship.shields > sd:
            if self.ship.shields > 50 and self.ship.shields - sd <= 50:
                self.message("Shields down to 50%",WARNING_MESSAGE_COLOR,True)
            self.ship.shields -= sd
        elif self.ship.shields > 0:
            hd += sd-self.ship.shields
            self.ship.shields = 0
            self.message("Shields are down!",ALERT_MESSAGE_COLOR,True)
        else:
            hd += sd
        if hd > sum(self.ship.health):
            self.ship.health = [0,0,0]
#            self.game_over()
            return
        if self.last_damage_frame >= self.frame-5:
            i = self.last_damage_type
        else:
            i = random.randrange(3)
        while hd > 0:
            match i:
                case 0: type = "Torpedo system"
                case 1: type = "Phasers"
                case 2: type = "Warp drive"
            if self.ship.health[i] > 50 and self.ship.health[i] - hd <= 50:
                self.message(type+" down to 50% health!",WARNING_MESSAGE_COLOR,True)
            if self.ship.health[i] > 0 and self.ship.health[i] - hd <= 0.5:
                self.message(type+" inoperative!",ALERT_MESSAGE_COLOR,True)
            self.ship.health[i] -= hd
            hd = 0
            if self.ship.health[i] < 0.5:
                if self.ship.health[i] < 0:
                    hd = 0-self.ship.health[i]
                self.ship.health[i] = 0
            self.last_damage_type = i
            i = random.randrange(3)
        self.last_damage_frame = self.frame


    def explosion(self,x,y,size):
        explosion = Explosion(self.explosion_textures, x, y, self.biggrid_wh[0]/400*size)
        explosion.angle = random.randrange(360)
        self.explosion_sprites.append(explosion)

    def update_navareas(self):
        self.navareas.clear()
        for r in range(self.sectors):
            for c in range(self.sectors):
                sector = self.universe[(r,c)]
                if sector.explored == True:
                    x,y = self.smallgrid_xy[r][c]
                    w,h = self.smallgrid_wh
                    g = w/9
                    w = w / 3
                    h = h / 3
                    for e in range(sector.enemies):
                        match e:
                            case 0:
                                xe = x - w + g
                                ye = y + h - g
                            case 1:
                                xe = x + w - g
                                ye = y + h - g
                            case 2:
                                xe = x - w + g
                                ye = y - h + g
                        self.navareas.append(shape_list.create_rectangle_filled(xe,ye,w,h,ENEMY_COLOR))
                    if sector.bases > 0:
                        xe = x + w - g
                        ye = y - h + g
                        self.navareas.append(shape_list.create_rectangle_filled(xe,ye,w,h,BASE_COLOR))
                else:
                    self.navareas.append(shape_list.create_rectangle_filled(*self.smallgrid_xy[r][c],*self.smallgrid_wh,FOG_COLOR))


    def on_draw(self):
        self.clear()
        self.camera.use()
        self.starfield_sprites.draw()
        self.gridlines.draw()
        self.navareas.draw()
        self.subgrid.draw()
        self.torp_sprites.draw()
        self.phaser_shapes.draw()
        self.enemy_sprites.draw()
        self.base_sprites.draw()
        self.star_sprites.draw()
        self.ship_sprites.draw()
        self.explosion_sprites.draw()
        r,c = self.sector.rc[0],self.sector.rc[1]
        arcade.draw_lbwh_rectangle_outline(*self.smallgrid_lb[r][c],*self.smallgrid_wh,arcade.color.WHITE,border_width=GRIDLINE_WIDTH)
        if self.button == "T":
            arcade.draw_lbwh_rectangle_outline(*self.torp_lb,*self.torp_wh,arcade.color.WHITE,border_width=GRIDLINE_WIDTH)
        if self.button == "P":
            arcade.draw_lbwh_rectangle_outline(*self.phaser_lb,*self.phaser_wh,arcade.color.WHITE,border_width=GRIDLINE_WIDTH)
        if self.button == "N":
            arcade.draw_lbwh_rectangle_outline(*self.nav_lb,*self.nav_wh,arcade.color.WHITE,border_width=GRIDLINE_WIDTH)

        w = self.phaser_status_wh[0]*(self.ship.energy/MAX_ENERGY)
        arcade.draw_lbwh_rectangle_outline(*self.phaser_status_lb,*self.phaser_status_wh,PHASER_COLOR,border_width=GRIDLINE_WIDTH)
        arcade.draw_lbwh_rectangle_filled(*self.phaser_status_lb,w,self.phaser_status_wh[1],PHASER_COLOR)

        self.ui_sprites.draw()
        self.ui_shapes.draw()
        self.debug_sprites.draw()
        self.debug_shapes.draw()
        # Shields
        self.torp_text2.text = str(round(self.ship.health[0]))+"%"
        self.phaser_text2.text = str(round(self.ship.health[1]))+"%"
        self.engine_text2.text = str(round(self.ship.health[2]))+"%"
        self.shield_text2.text = str(round(self.ship.shields))+"%"
        self.enemies_text2.text = self.enemies
        self.days_text2.text = self.days

        self.ui_text.draw()
        if self.scrollbar:
            arcade.draw_lbwh_rectangle_filled(*self.scrollbar,arcade.color.LIGHT_GRAY)

    def move_ship(self,r,c,docking):
        if docking:
            self.base = self.sector.grid[(r,c)]
        self.sector.grid[(r,c)] = self.sector.grid.pop(self.ship.rc)
        if self.ship.docked:
            self.sector.grid[(self.ship.rc)] = self.base
        self.ship.move_to(self,r,c,docking)

    def on_mouse_press(self, x, y, button, modifiers):
        x, y, z = self.camera.unproject((x,y))
        if self.warping > 0: return
        if self.small_lb[0] <= x <= self.small_lb[0]+self.small_wh[0] and self.small_lb[1] <= y <= self.small_lb[1]+self.small_wh[1]:
            # clicked in the navigation area
            if self.ship.health[2] == 0:
                self.message("Warp core is offline!",WARNING_MESSAGE_COLOR,False)
                return
            for r in range(self.sectors):
                for c in range(self.sectors):
                    gx,gy = self.smallgrid_lb[r][c][0],self.smallgrid_lb[r][c][1]
                    w,h = self.smallgrid_wh[0],self.smallgrid_wh[1]
                    if gx <= x <= gx+w and gy <= y <= gy+h:
                        # clicked sector r,c
                        if self.sector.rc == (r,c):
                            return
                        self.warping = 1
                        self.warp_sector = (r,c)
                        return
        if self.big_lb[0] <= x <= self.big_lb[0]+self.big_wh[0] and self.big_lb[1] <= y <= self.big_lb[1]+self.big_wh[1]:
            # clicked in the main grid
            if self.ship.moving == True: return
            match self.button:
                case "N":
                    for r in range(self.cells):
                        for c in range(self.cells):
                            gx,gy = self.biggrid_lb[r][c][0],self.biggrid_lb[r][c][1]
                            w,h = self.biggrid_wh[0],self.biggrid_wh[1]
                            if gx <= x <= gx+w and gy <= y <= gy+h:
                                # clicked cell r,c
                                if (r,c) not in self.sector.grid:
                                    # empty space, move to that location
                                    self.move_ship(r,c,False)
                                else:
                                    cell = self.sector.grid[(r,c)]
                                    if cell.type == "B":
                                        if self.sector.enemies > 0:
                                            # TEMPTEMP Can't dock with enemies nearby
                                            return
                                        self.move_ship(r,c,True)
                                return
                case "T":
                    # Fire torpedoes
                    if self.currently_firing > 0: return
                    self.ship.fire_to(self,x,y,"T")
                    self.ship.torpedoes -= 1
                    if self.ship.torpedoes == 0:
                        self.button = None
                case "P":
                    # Fire phasers
                    if self.currently_firing > 0: return
                    self.ship.fire_to(self,x,y,"P")
                    self.firing_phasers = True
                case _:
                    self.message("Select to navigate or fire a weapon first",WARNING_MESSAGE_COLOR,False)
        if self.ship.docking == True:
            return
        if self.nav_lb[0] <= x <= self.nav_lb[0]+self.nav_wh[0] and self.nav_lb[1] <= y <= self.nav_lb[1]+self.nav_wh[1]:
            # clicked the nav button
            if self.button == "N":
                self.button = None
            else:
                self.message("Impulse drive engaged",INFO_MESSSAGE_COLOR,False)
                self.button = "N"
        if self.torp_lb[0] <= x <= self.torp_lb[0]+self.torp_wh[0] and self.torp_lb[1] <= y <= self.torp_lb[1]+self.torp_wh[1]:
            # clicked the torpedo button
            if self.ship.docked:
                self.message("Can't fire torpedoes while docked!",WARNING_MESSAGE_COLOR,False)
                return
            if self.ship.health[0] == 0:
                self.message("Torpedoes are inoperative!",WARNING_MESSAGE_COLOR,False)
                return
            if self.ship.torpedoes == 0:
                self.message("Out of torpedoes!",WARNING_MESSAGE_COLOR,False)
                return
            if self.button == "T":
                self.button = None
            else:
                self.message("Torpedoes armed!",ALERT_MESSAGE_COLOR,False)
                self.button = "T"
        if self.phaser_lb[0] <= x <= self.phaser_lb[0]+self.phaser_wh[0] and self.phaser_lb[1] <= y <= self.phaser_lb[1]+self.phaser_wh[1]:
            # clicked the phaser button
            if self.ship.docked:
                self.message("Can't fire phasers while docked!",WARNING_MESSAGE_COLOR,False)
                return
            if self.ship.health[1] == 0:
                self.message("Phasers are inoperative!",WARNING_MESSAGE_COLOR,False)
                return
            if self.ship.energy == 0:
                self.message("Phaser banks depleted!",WARNING_MESSAGE_COLOR,False)
                return
            if self.button == "P":
                self.button = None
            else:
                self.message("Phasers armed!",ALERT_MESSAGE_COLOR,False)
                self.button = "P"
        if self.repair_lb[0] <= x <= self.repair_lb[0]+self.repair_wh[0] and self.repair_lb[1] <= y <= self.repair_lb[1]+self.repair_wh[1]:
            # clicked the repair button
            if self.sector.enemies > 0:
                self.message("Cannot repair with enemies nearby",WARNING_MESSAGE_COLOR,False)
                return
            delay = self.repairs(False)
            match delay:
                case 0:
                    msg = "Repairs completed in under a day"
                case 1:
                    msg = "Repairs took 1 day to complete"
                case _:
                    msg = f"Repairs took {delay} days to complete"
            self.message(msg,INFO_MESSSAGE_COLOR,True)
        if self.log_lb[0] <= x <= self.log_lb[0]+self.log_wh[0] and self.log_lb[1] <= y <= self.log_lb[1]+self.log_wh[1]:
            self.drag_remainder = 0

    def on_mouse_release(self, x, y, button, modifiers):
        x, y, z = self.camera.unproject((x,y))
        self.firing_phasers = False
        self.drag_remainder = None

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        x, y, z = self.camera.unproject((x,y))
        if self.log_lb[0] <= x <= self.log_lb[0]+self.log_wh[0] and self.log_lb[1] <= y <= self.log_lb[1]+self.log_wh[1]:
            # scrolling the log window
            max_scroll = max(0, len(self.log)-len(self.log_message))
            self.log_scroll += scroll_y
            self.log_scroll = round(min(max(0,self.log_scroll),max_scroll))

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        x, y, z = self.camera.unproject((x,y))
        if self.drag_remainder != None:
            self.drag_remainder += dy
            lines = int(self.drag_remainder // self.log_height)
            if lines != 0:
                self.log_scroll += lines
                self.drag_remainder -= (lines*self.log_height)
                max_scroll = max(0, len(self.log)-len(self.log_message))
                self.log_scroll = round(min(max(0,self.log_scroll),max_scroll))

    def on_close(self):
        super().on_close()

async def main_web():
    window = MyGame()
    window.setup()
    while True:
        await asyncio.sleep(0)

def main_desktop():
    window = MyGame()
    window.setup()
    arcade.run()

if __name__ == "__main__":
    if sys.platform == "emscripten" or "pygbag" in sys.modules:
        asyncio.run(main_web())
    else:
        main_desktop()
