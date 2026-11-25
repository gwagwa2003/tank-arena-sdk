"""Arena constants: maps, chassis, modules, timings. Same values as the Tank Arena server."""

MAPS = {
    "fort": dict(name="十字堡壘", rects=[(370, 260, 60, 280), (260, 370, 280, 60), (130, 140, 100, 36), (570, 140, 100, 36),
                                     (130, 624, 100, 36), (570, 624, 100, 36), (90, 370, 40, 60), (670, 370, 40, 60)]),
    "city": dict(name="城區巷戰", rects=[(170, 180, 130, 56), (510, 150, 56, 150), (345, 345, 110, 110), (150, 510, 56, 150), (500, 565, 150, 56),
                                     (40, 385, 110, 30), (650, 385, 110, 30), (370, 70, 60, 44), (370, 686, 60, 44)]),
}
# chassis: speed (px/step), body turn (rad/step), reload (steps), bullet speed, bullet life (steps), HP
CHASSIS = dict(gunner=(3.0, .070, 12, 11, 55, 90), shotgun=(3.0, .070, 38, 11, 30, 96),
               skirmisher=(3.5, .080, 10, 12.5, 25, 110), marksman=(2.8, .070, 22, 11, 55, 120))
DAMAGE = dict(skirmisher=10, marksman=18)  # damage per bullet; every other chassis does 12 (shotgun: see SHOT_FALLOFF)
SIEGE_WAIT, SIEGE_RELOAD, SIEGE_BSPD = 30, 14, 13.0  # retired chassis siege (engine still knows it for old data)
SHOT_N, SHOT_SPREAD = 3, 0.30  # shotgun: pellets per shot, angle between neighbours (rad)
SHOT_FALLOFF = (14, 7, 6, 14)  # shotgun pellet: 14 damage while it has flown <= 6 steps (~66 px), then down to 7 at 14 steps (~154 px)
# active modules: duration, cooldown (steps); radar is passive
MODULES = dict(stealth=(50, 480), shield=(40, 400), backstep=(2, 160), focus=(40, 180))
SMOKE_R, OVERDRIVE = 60, 0.75  # retired modules smoke / overdrive (engine still knows them for old data)
BLINK = 80  # stealth: jump this far (px) along the move direction when it starts; stops in front of walls
BACKSTEP = 24  # backstep: on the step after pressing, hop this far (px) straight away from where the turret points
FOCUS_BSPD, FOCUS_MOVE = 14.0, 0.78  # focus: bullet speed while it is on, and moving speed x this
ALL_MODULES = ["stealth", "shield", "radar", "backstep", "focus"]
ARENA, TR, TROT, STEPS = 800, 16, 0.11, 1200

CHASSIS_INFO = {  # same six items for every chassis; range = bullet speed x bullet life
    "gunner": "速射：速度 3.0、裝填 12、傷害 12、子彈速度 11、射程約 605、血量 90",
    "shotgun": "散彈：速度 3.0、裝填 38、一次 3 顆（約 66 內每顆 14 傷害，越遠越低，約 154 外 7）、子彈速度 11、射程約 330、血量 96",
    "skirmisher": "遊擊：速度 3.5、轉向較快、裝填 10、傷害 10、子彈速度 12.5、射程約 310、血量 110",
    "marksman": "狙擊：速度 2.8、裝填 22、傷害 18、子彈速度 11、射程約 605、血量 120",
}
MODULE_INFO = {
    "stealth": "隱身：啟動時往移動方向閃現 80（後退時往後、撞牆就停），之後 2.5 秒內不出現在敵人觀測裡、冷卻 24 秒，開火就解除",
    "shield": "護盾：2 秒內擋下一發子彈、冷卻 20 秒",
    "radar": "雷達：視線 340 → 450，但別人也更早看到你（被動）",
    "backstep": "後跳：按下後下一步往砲塔的反方向跳 24（撞牆就停）、冷卻 8 秒",
    "focus": "專注：2 秒內子彈速度變 14、移動速度變 78%、冷卻 9 秒",
}


def hits_rect(x, y, rad, r):
    nx = max(r["x"], min(x, r["x"] + r["w"])); ny = max(r["y"], min(y, r["y"] + r["h"]))
    return (x - nx) ** 2 + (y - ny) ** 2 < rad * rad
