"""Arena constants: maps, chassis, modules, timings. Same values as the Tank Arena server."""

MAPS = {
    "fort": dict(name="十字堡壘", rects=[(370, 260, 60, 280), (260, 370, 280, 60), (130, 140, 100, 36), (570, 140, 100, 36),
                                     (130, 624, 100, 36), (570, 624, 100, 36), (90, 370, 40, 60), (670, 370, 40, 60)]),
    "city": dict(name="城區巷戰", rects=[(170, 180, 130, 56), (510, 150, 56, 150), (345, 345, 110, 110), (150, 510, 56, 150), (500, 565, 150, 56),
                                     (40, 385, 110, 30), (650, 385, 110, 30), (370, 70, 60, 44), (370, 686, 60, 44)]),
}
# chassis: speed (px/step), body turn (rad/step), reload (steps), bullet speed, bullet life (steps), HP
CHASSIS = dict(standard=(3.0, .070, 18, 11, 70, 100), heavy=(2.5, .060, 18, 11, 70, 120), scout=(3.8, .075, 18, 11, 70, 80),
               gunner=(3.0, .070, 12, 11, 55, 90), lancer=(3.0, .070, 26, 12.5, 70, 100))
# active modules: duration, cooldown (steps); antizone and radar are passive
MODULES = dict(stealth=(50, 480), shield=(40, 400), boost=(20, 120))
ALL_MODULES = ["stealth", "shield", "boost", "antizone", "radar"]
ARENA, TR, TROT, STEPS = 800, 16, 0.11, 1200

CHASSIS_INFO = {  # same five items for every chassis; range = bullet speed x bullet life
    "standard": "標準：速度 3.0、裝填 18、子彈速度 11、射程約 770、血量 100",
    "heavy": "重裝：速度 2.5、裝填 18、子彈速度 11、射程約 770、血量 120",
    "scout": "輕裝：速度 3.8、裝填 18、子彈速度 11、射程約 770、血量 80",
    "gunner": "速射：速度 3.0、裝填 12、子彈速度 11、射程約 605、血量 90",
    "lancer": "長砲：速度 3.0、裝填 26、子彈速度 12.5、射程約 875、血量 100",
}
MODULE_INFO = {
    "stealth": "隱身：2.5 秒內不出現在敵人觀測裡、冷卻 24 秒，開火就解除",
    "shield": "護盾：2 秒內擋下一發子彈、冷卻 20 秒",
    "boost": "衝刺：1 秒內速度 ×2、不能開火、冷卻 6 秒",
    "antizone": "抗毒：圈外傷害減半（被動）",
    "radar": "雷達：視線 340 → 450，但別人也更早看到你（被動）",
}


def hits_rect(x, y, rad, r):
    nx = max(r["x"], min(x, r["x"] + r["w"])); ny = max(r["y"], min(y, r["y"] + r["h"]))
    return (x - nx) ** 2 + (y - ny) ** 2 < rad * rad
