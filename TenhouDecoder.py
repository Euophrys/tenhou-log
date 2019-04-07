#! /usr/bin/python3
#! /usr/bin/python3
# -*- coding: utf-8 -*-

from inspect import getsourcefile
import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as etree

from Data import Data

class Tile(Data, int):
    UNICODE_TILES = """
        🀐 🀑 🀒 🀓 🀔 🀕 🀖 🀗 🀘
        🀙 🀚 🀛 🀜 🀝 🀞 🀟 🀠 🀡
        🀇 🀈 🀉 🀊 🀋 🀌 🀍 🀎 🀏
        🀀 🀁 🀂 🀃
        🀆 🀅 🀄
    """.split()

    TILES = """
        1s 2s 3s 4s 5s 6s 7s 8s 9s
        1p 2p 3p 4p 5p 6p 7p 8p 9p
        1m 2m 3m 4m 5m 6m 7m 8m 9m
        ew sw ww nw
        wd gd rd
    """.split()

    def asdata(self, ignored):
        return self.TILES[self // 4] + str(self % 4)

class Player(Data):
    def __init__(self):
        self.name = ""
        self.rank = ""
        self.sex = ""
        self.rate = 0
        self.connected = True

class Round(Data):
    def __init__(self):
        self.dealer = 0
        self.hands = tuple() # Tile tuple tuple
        self.round = tuple() # Tuple of string (name), int (honba count), int (leftover riichi sticks)
        self.agari = []
        self.events = []
        self.ryuukyoku = False # Can also be a string, if it's special
        self.ryuukyoku_tenpai = None
        self.reaches = [0, 0, 0, 0] # What turn it was when each player reached
        self.reach_turns = [] # What turns reaches happened on
        self.turns = [0, 0, 0, 0] # What turn it is for each player
        self.deltas = [] # Score changes

class Meld(Data):
    @classmethod
    def decode(Meld, data):
        data = int(data)
        meld = Meld()
        meld.fromPlayer = data & 0x3
        if data & 0x4:
            meld.decodeChi(data)
        elif data & 0x18:
            meld.decodePon(data)
        elif data & 0x20:
            meld.decodeNuki(data)
        else:
            meld.decodeKan(data)
        return meld

    def decodeChi(self, data):
        self.type = "chi"
        t0, t1, t2 = (data >> 3) & 0x3, (data >> 5) & 0x3, (data >> 7) & 0x3
        baseAndCalled = data >> 10
        self.called = baseAndCalled % 3
        base = baseAndCalled // 3
        base = (base // 7) * 9 + base % 7
        self.tiles = Tile(t0 + 4 * (base + 0)), Tile(t1 + 4 * (base + 1)), Tile(t2 + 4 * (base + 2))

    def decodePon(self, data):
        t4 = (data >> 5) & 0x3
        t0, t1, t2 = ((1, 2, 3), (0, 2, 3), (0, 1, 3), (0, 1, 2))[t4]
        baseAndCalled = data >> 9
        self.called = baseAndCalled % 3
        base = baseAndCalled // 3
        if data & 0x8:
            self.type = "pon"
            self.tiles = Tile(t0 + 4 * base), Tile(t1 + 4 * base), Tile(t2 + 4 * base)
        else:
            self.type = "chakan"
            self.tiles = Tile(t0 + 4 * base), Tile(t1 + 4 * base), Tile(t2 + 4 * base), Tile(t4 + 4 * base)

    def decodeKan(self, data):
        baseAndCalled = data >> 8
        if self.fromPlayer:
            self.called = baseAndCalled % 4
        else:
            del self.fromPlayer
        base = baseAndCalled // 4
        self.type = "kan"
        self.tiles = Tile(4 * base), Tile(1 + 4 * base), Tile(2 + 4 * base), Tile(3 + 4 * base)

    def decodeNuki(self, data):
        del self.fromPlayer
        self.type = "nuki"
        self.tiles = Tile(data >> 8)

class Event(Data):
    def __init__(self, events):
        events.append(self)
        self.type = type(self).__name__

class Dora(Event):
    def __init__(self, events):
        Event.__init__(self, events)
        self.tile = 0

class Draw(Event):
    def __init__(self, events):
        Event.__init__(self, events)
        self.tile = 0
        self.player = 0

class Discard(Event):
    def __init__(self, events):
        Event.__init__(self, events)
        self.tile = None
        self.player = 0
        self.connected = True    

class Call(Event):
    def __init__(self, events):
        Event.__init__(self, events)
        self.meld = None
        self.player = 0

class Riichi(Event):
    pass

class Agari(Data):
    def __init__(self):
        self.type = "" # Either "RON" or "TSUMO"
        self.player = 0
        self.hand = tuple() # of Tile
        self.fu = 0
        self.points = 0
        self.limit = "" # eg, "mangan"
        self.dora = tuple() # of Tile
        self.machi = tuple() # of Tile
        self.melds = tuple() # of Meld
        self.closed = True
        self.uradora = tuple() # of Tile
        self.fromPlayer = 0 # only meaningful if type == "RON"
        self.yaku = tuple() # of strings
        self.yakuman = tuple() # of strings

class Game(Data):
    RANKS = "新人,9級,8級,7級,6級,5級,4級,3級,2級,1級,初段,二段,三段,四段,五段,六段,七段,八段,九段,十段,天鳳位".split(",")
    NAMES = "n0,n1,n2,n3".split(",")
    HANDS = "hai0,hai1,hai2,hai3".split(",")
    ROUND_NAMES = "東1,東2,東3,東4,南1,南2,南3,南4,西1,西2,西3,西4,北1,北2,北3,北4".split(",")
    YAKU_NAMES = {}
    YAKU = {
        # one-han yaku
        0:'門前清自摸和',     # menzen tsumo
        1:'立直',           # riichi
        2:'一発',           # ippatsu
        3:'槍槓',           # chankan
        4:'嶺上開花',        # rinshan kaihou
        5:'海底摸月',        # haitei raoyue
        6:'河底撈魚',        # houtei raoyui
        7:'平和',           # pinfu
        8:'断幺九',         # tanyao
        9:'一盃口',         # iipeiko
        # seat winds
        10:'自風 東',       # ton
        11:'自風 南',       # nan
        12:'自風 西',       # xia
        13:'自風 北',       # pei
        # round winds
        14:'場風 東',       # ton
        15:'場風 南',       # nan
        16:'場風 西',       # xia
        17:'場風 北',       # pei
        18:'役牌 白',       # haku
        19:'役牌 發',       # hatsu
        20:'役牌 中',       # chun
        # two-han yaku
        21:'両立直',        # daburu riichi
        22:'七対子',        # chiitoitsu
        23:'混全帯幺九',     # chanta
        24:'一気通貫',       # ittsu
        25:'三色同順',       # sanshoku doujun
        26:'三色同刻',       # sanshoku doukou
        27:'三槓子',        # sankantsu
        28:'対々和',        # toitoi
        29:'三暗刻',        # sanankou
        30:'小三元',        # shousangen
        31:'混老頭',        # honroutou
        # three-han yaku
        32:'二盃口',        # ryanpeikou
        33:'純全帯幺九',     # junchan
        34:'混一色',        # honitsu
        # six-han yaku
        35:'清一色',        # chinitsu
        # unused
        36:'人和',          # renhou
        # yakuman
        37:'天和',          # tenhou
        38:'地和',          # chihou
        39:'大三元',        # daisangen
        40:'四暗刻',        # suuankou
        41:'四暗刻単騎',     # suuankou tanki
        42:'字一色',        # tsuuiisou
        43:'緑一色',        # ryuuiisou
        44:'清老頭',        # chinroutou
        45:'九蓮宝燈',       # chuuren pouto
        46:'純正九蓮宝燈',    # chuuren pouto 9-wait
        47:'国士無双',       # kokushi musou
        48:'国士無双１３面',   # kokushi musou 13-wait
        49:'大四喜',        # daisuushi
        50:'小四喜',        # shousuushi
        51:'四槓子',        # suukantsu
        # dora
        52:'ドラ',          # dora
        53:'裏ドラ',         # uradora
        54:'赤ドラ',         # akadora
        }

    LIMITS = ",mangan,haneman,baiman,sanbaiman,yakuman".split(",")

    TAGS = {}

    def __init__(self, lang, suppress_draws=False):
        self.suppress_draws = suppress_draws
        self.lang = lang
        self.gameType = ""
        self.lobby = ""
        self.players = []
        self.round = Round()
        self.rounds = []
        self.owari = ""

    def tagGO(self, tag, data):
        # The <GO lobby=""/> attribute was introduced at some point between
        # 2010 and 2012:
        self.gameType = data["type"]
        self.lobby = data.get("lobby")

    def tagUN(self, tag, data):
        if "dan" in data:
            for name in self.NAMES:
                # An empty name, along with sex C, rank 0 and rate 1500 are
                # used as placeholders in the fourth player fields in
                # three-player games
                if data[name]:
                    player = Player()
                    player.name = urllib.parse.unquote(data[name])
                    self.players.append(player)
            ranks = self.decodeList(data["dan"])
            sexes = self.decodeList(data["sx"], dtype=str)
            rates = self.decodeList(data["rate"], dtype=float)
            for (player, rank, sex, rate) in zip(self.players, ranks, sexes, rates):
                player.rank = self.RANKS[rank]
                player.sex = sex
                player.rate = rate
                player.connected = True
        else:
            for (player, name) in zip(self.players, self.NAMES):
                if name in data:
                    player.connected = True

    def tagBYE(self, tag, data):
        self.players[int(data["who"])].connected = False

    def tagINIT(self, tag, data):
        name, combo, riichi, d0, d1, dora = self.decodeList(data["seed"])
        self.round = Round()
        self.rounds.append(self.round)
        self.round.dealer = int(data["oya"])
        self.round.hands = tuple(self.decodeList(data[hand], Tile) for hand in self.HANDS if hand in data and data[hand])
        self.round.round = self.ROUND_NAMES[name % len(self.ROUND_NAMES)], combo, riichi

        Dora(self.round.events).tile = Tile(dora)

    def tagN(self, tag, data):
        call = Call(self.round.events)
        call.meld = Meld.decode(data["m"])
        call.player = int(data["who"])
        self.round.turns[call.player] += 1

    def tagTAIKYOKU(self, tag, data):
        pass

    def tagDORA(self, tag, data):
        Dora(self.round.events).tile = int(data["hai"])

    def tagRYUUKYOKU(self, tag, data):
        self.round.ryuukyoku = True

        deltas = data['sc'].split(',')
        self.round.deltas = [int(deltas[x]) for x in range(1,8,2)]

        if 'owari' in data:
            self.owari = data['owari']
        # For special ryuukyoku types, set to string ID rather than boolean
        if 'type' in data:
            self.round.ryuukyoku = data['type']
        if self.round.ryuukyoku is True or self.round.ryuukyoku == "nm":
            tenpai = self.round.ryuukyoku_tenpai = []
            for index, attr_name in enumerate(self.HANDS):
                if attr_name in data:
                    tenpai.append(index)

    def tagAGARI(self, tag, data):
        agari = Agari()
        self.round.agari.append(agari)
        agari.type = "RON" if data["fromWho"] != data["who"] else "TSUMO"
        agari.player = int(data["who"])
        agari.hand = self.decodeList(data["hai"], Tile)

        deltas = data['sc'].split(',')
        self.round.deltas = [int(deltas[x]) for x in range(1,8,2)]

        agari.fu, agari.points, limit = self.decodeList(data["ten"])
        if limit:
            agari.limit = self.LIMITS[limit]
        agari.dora = self.decodeList(data["doraHai"], Tile)
        agari.machi = self.decodeList(data["machi"], Tile)
        if "m" in data:
            agari.melds = self.decodeList(data["m"], Meld.decode)
            agari.closed = all(not hasattr(meld, "fromPlayer") for meld in agari.melds)
        else:
            agari.closed = True
        if "dorahaiUra" in data:
            agari.uradora = self.decodeList(data["uradoraHai"], Tile)
        if agari.type == "RON":
            agari.fromPlayer = int(data["fromWho"])
        if "yaku" in data:
            yakuList = self.decodeList(data["yaku"])
            agari.yaku = tuple(
                (self.YAKU_NAMES[self.YAKU[yaku]][self.lang], han)
                for yaku, han in zip(yakuList[::2], yakuList[1::2]))
        if "yakuman" in data:
            agari.yakuman = tuple(
                self.YAKU_NAMES[self.YAKU[yaku]][self.lang]
                for yaku in self.decodeList(data["yakuman"]))
        if 'owari' in data:
            self.owari = data['owari']

    def tagREACH(self, tag, data):
        if 'ten' in data:
            player = int(data['who'])
            self.round.reaches.append(player)
            self.round.reach_turns.append(self.round.turns[player])

    @staticmethod
    def default(obj, tag, data):
        if obj.suppress_draws:
            return
        if tag[0] in "DEFG":
            discard = Discard(obj.round.events)
            discard.tile = Tile(tag[1:])
            discard.player = ord(tag[0]) - ord("D")
            discard.connected = obj.players[discard.player].connected
        elif tag[0] in "TUVW":
            draw = Draw(obj.round.events)
            draw.tile = Tile(tag[1:])
            draw.player = ord(tag[0]) - ord("T")
            obj.round.turns[draw.player] += 1
        else:
            pass

    @staticmethod
    def decodeList(thislist, dtype=int):
        return tuple(dtype(i) for i in thislist.split(","))

    def decode(self, log):
        try:
            events = etree.parse(log).getroot()
        except:
            try:
                events = etree.fromstring(log)
            except:
                return
        self.rounds = []
        self.players = []
        for event in events:
            self.TAGS.get(event.tag, self.default)(self, event.tag, event.attrib)
        del self.round

# %% get the yaku translations from the tenhou translator ui

thisdir = os.path.dirname(os.path.abspath(getsourcefile(lambda: 0)))
with open(os.path.join(thisdir, 'translations.js'), 'r', encoding='utf-8') as infile:
    txt = infile.read()
txt1 = txt[txt.find('{') : txt.find('\n};\n')+2]
txt15 = re.sub(r'//[^\n]+\n', '\n', txt1)
txt2 = re.sub(r"(\n *)'([^']+)'(:)", r'\1"\2"\3', txt15)
txt3 = re.sub(r"(: *)'([^\n]+)'(,)", r'\1"\2"\3', txt2)
txt4 = txt3.replace('\n', '')
txt5 = re.sub(r',[\n ]*}', '}', txt4)
txt6 = re.sub(r'\n', '', txt5)
txt7 = re.sub(r"\\'", "'", txt6)
Game.YAKU_NAMES = json.loads(txt7)

# %%

for key in Game.__dict__:
    if key.startswith('tag'):
        Game.TAGS[key[3:]] = getattr(Game, key)

if __name__ == '__main__':
    import yaml
    import sys
    for path in sys.argv[1:]:
        game = Game('DEFAULT')
        game.decode(open(path))
        yaml.dump(game.asdata(), sys.stdout, default_flow_style=False, allow_unicode=True)
