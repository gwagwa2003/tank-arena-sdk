"""Arena constants: maps, chassis, modules, timings. Same values as the Tank Arena server."""

MAPS = {
    "fort": dict(name="十字堡壘", rects=[(370, 260, 60, 280), (260, 370, 280, 60), (130, 140, 100, 36), (570, 140, 100, 36),
                                     (130, 624, 100, 36), (570, 624, 100, 36), (90, 370, 40, 60), (670, 370, 40, 60)]),
    "city": dict(name="城區巷戰", rects=[(170, 180, 130, 56), (510, 150, 56, 150), (345, 345, 110, 110), (150, 510, 56, 150), (500, 565, 150, 56),
                                     (40, 385, 110, 30), (650, 385, 110, 30), (370, 70, 60, 44), (370, 686, 60, 44)]),
}
# chassis: speed (px/step), body turn (rad/step), reload (steps), bullet speed, bullet life (steps), HP
CHASSIS = dict(standard=(3.0, .070, 15, 11, 70, 100), heavy=(2.5, .060, 18, 11, 70, 120), scout=(5.0, .075, 18, 11, 70, 90),
               gunner=(3.0, .070, 12, 11, 55, 90), lancer=(3.0, .070, 26, 12.5, 70, 100),
               siege=(2.6, .070, 18, 11, 70, 115), shotgun=(3.0, .070, 38, 11, 30, 96))
DAMAGE = dict(lancer=15)  # damage per bullet; every other chassis does 12 (shotgun: see SHOT_FALLOFF)
SIEGE_WAIT, SIEGE_RELOAD, SIEGE_BSPD = 30, 14, 13.0  # siege: after standing still this many steps, reload and bullet speed
SHOT_N, SHOT_SPREAD = 3, 0.30  # shotgun: pellets per shot, angle between neighbours (rad)
SHOT_FALLOFF = (14, 7, 6, 14)  # shotgun pellet: 14 damage while it has flown <= 6 steps (~66 px), then down to 7 at 14 steps (~154 px)
# active modules: duration, cooldown (steps); antizone and radar are passive
MODULES = dict(stealth=(50, 480), shield=(40, 400), xray=(60, 400), smoke=(80, 440), overdrive=(60, 480))
SMOKE_R = 60  # smoke: radius of the cloud, left where the tank stood
OVERDRIVE = 0.75  # overdrive: reload x this while it is on
BLINK = 80  # stealth: jump this far (px) along the move direction when it starts; stops in front of walls
ALL_MODULES = ["stealth", "shield", "antizone", "radar", "xray", "smoke", "overdrive"]
ARENA, TR, TROT, STEPS = 800, 16, 0.11, 1200

CHASSIS_INFO = {  # same six items for every chassis; range = bullet speed x bullet life
    "standard": "標準：速度 3.0、裝填 15、傷害 12、子彈速度 11、射程約 770、血量 100",
    "heavy": "重裝：速度 2.5、裝填 18、傷害 12、子彈速度 11、射程約 770、血量 120",
    "scout": "輕裝：速度 5.0、裝填 18、傷害 12、子彈速度 11、射程約 770、血量 90",
    "gunner": "速射：速度 3.0、裝填 12、傷害 12、子彈速度 11、射程約 605、血量 90",
    "lancer": "長砲：速度 3.0、裝填 26、傷害 15、子彈速度 12.5、射程約 875、血量 100",
    "siege": "攻城：速度 2.6、裝填 18（停住 1.5 秒後 14）、傷害 12、子彈速度 11（停住後 13）、射程約 770、血量 115",
    "shotgun": "散彈：速度 3.0、裝填 38、一次 3 顆（約 66 內每顆 14 傷害，越遠越低，約 154 外 7）、子彈速度 11、射程約 330、血量 96",
}
MODULE_INFO = {
    "stealth": "隱身：啟動時往移動方向閃現 80（後退時往後、撞牆就停），之後 2.5 秒內不出現在敵人觀測裡、冷卻 24 秒，開火就解除",
    "shield": "護盾：2 秒內擋下一發子彈、冷卻 20 秒",
    "antizone": "抗毒：圈外傷害減半（被動）",
    "radar": "雷達：視線 340 → 450，但別人也更早看到你（被動）",
    "xray": "透視：3 秒內視線不被牆擋（距離不變、看不到隱身）、冷卻 20 秒",
    "smoke": "煙霧：在原地放一團半徑 60 的煙，4 秒內擋住雙方視線（子彈照樣穿過、透視看得穿）、冷卻 22 秒",
    "overdrive": "過載：3 秒內裝填快 25%、冷卻 24 秒",
}


def hits_rect(x, y, rad, r):
    nx = max(r["x"], min(x, r["x"] + r["w"])); ny = max(r["y"], min(y, r["y"] + r["h"]))
    return (x - nx) ** 2 + (y - ny) ** 2 < rad * rad
