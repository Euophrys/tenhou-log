#! /usr/bin/python3

import TenhouDecoder
import collections
from Data import Data

YakuHanCounter = collections.namedtuple('YakuHanCounter', 'yaku han')

class YakuCounter(Data):
    def __init__(self, player = None, winner = None):
        self.player = player
        self.winner = winner
        self.hands = collections.Counter()
        self.relevantHands = collections.Counter()
        self.closed = YakuHanCounter(collections.Counter(), collections.Counter())
        self.opened = YakuHanCounter(collections.Counter(), collections.Counter())
        self.all = YakuHanCounter(collections.Counter(), collections.Counter())
        self.reach_outcomes = []
        self.player_index = 0

    def addGame(self, game):
        try:
            self.player_index = None
            for idx, player in enumerate(game.players):
                if player.name == self.player:
                    self.player_index = idx
                    break
            for round in game.rounds:
                self.addRound(round)
        except:
            return
            
    def addRound(self, round):
        for agari in round.agari:
            self.addAgari(agari)
        try:
            when_did_i_reach = round.reaches.index(self.player_index)
            self.reach_outcomes.append({
                'pursuit': when_did_i_reach,
                'turn': round.reach_turns[when_did_i_reach],
                'reach_count': len(round.reaches),
                'points': round.deltas[self.player_index] - 10,
                'type': round.agari[0].type if round.ryuukyoku is False else 'DRAW',
            })
        except ValueError:
            pass


    def addAgari(self, agari):
        counterYaku, counterHan = self.closed if agari.closed else self.opened
        allCounterYaku, allCounterHan = self.all
        self.hands["closed" if agari.closed else "opened"] += 1
        if (
            self.player is not None
            and self.winner is True
            and self.player_index != agari.player
            ) or (
            self.player is not None
            and self.winner is False
            and (
                not hasattr(agari, 'fromPlayer')
                or self.player_index != agari.fromPlayer
            )):
            return
        self.relevantHands["closed" if agari.closed else "opened"] += 1
        if hasattr(agari, 'yaku'):
            for yaku, han in agari.yaku:
                # yaku is the name, e.g. "Riichi", not an index
                if han > 0:
                    counterYaku[yaku] += 1
                    counterHan[yaku] += han
                    allCounterYaku[yaku] += 1
                    allCounterHan[yaku] += han
        if hasattr(agari, 'yakuman'):
            for yakuman in agari.yakuman:
                key = '___'+yakuman
                counterYaku[key] += 1
                counterHan[key] += 13
                allCounterYaku[key] += 1
                allCounterHan[key] += 13

if __name__ == '__main__':
    import sys
    import yaml
    counter = YakuCounter(None)
    for path in sys.argv[1:]:
        game = TenhouDecoder.Game()
        print(path)
        game.decode(open(path))
        counter.addGame(game)
    yaml.dump(counter.asdata(), sys.stdout, default_flow_style=False, allow_unicode=True)
