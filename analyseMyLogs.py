"""
sum yakus won and lost by one player, from available logs
"""

# core libraries
import argparse
import lzma
import pickle
import sys

# third-party libraries
import yaml

# own imports
from TenhouConfig import account_names, directory_name
import TenhouDecoder
import TenhouYaku

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument(
    '-w', '--winner',
    help='only count yakus for when the user won the hand (default)',
    action='store_true')
group.add_argument(
    '-l', '--loser',
    help='only count yakus for when the user lost the hand',
    action='store_true')
group.add_argument(
    '-a', '--all',
    help='count yakus from all hands',
    action='store_true')

parser.add_argument(
    '--since',
    help='date in yyyymmdd format: only include games since this date',
    action='store')

parser.add_argument(
    '--before',
    help='date in yyyymmdd format: only include games before this date',
    action='store')

args = parser.parse_args()

# %% accumulate stats across logged games

# default to only showing yaku counts for winning hands, unless command-line args specify otherwise
won_hands_only = False if args.loser is True else (None if args.all is True else True)
counter = TenhouYaku.YakuCounter(winner = won_hands_only)

TURNS = 25

gamecount = 0
outcomes = [
    [[0, 0], [0, 0], [0, 0]],
    [[0, 0], [0, 0], [0, 0]],
    [[0, 0], [0, 0], [0, 0]],
    [[0, 0], [0, 0], [0, 0]],
    [[0, 0], [0, 0], [0, 0]],
    [[0, 0], [0, 0], [0, 0]],
]

reach_turn_points = [[0] * TURNS, [0] * TURNS, [0] * TURNS, [0] * TURNS, [0] * TURNS]
reach_turn_counts = [[0] * TURNS, [0] * TURNS, [0] * TURNS, [0] * TURNS, [0] * TURNS]

outcome_names = ('I won', 'Draw', 'Bystander', 'Other tsumod', 'I dealt in', 'Averages')
for player in account_names:
    counter.player = player
    with lzma.open(directory_name + player + '.pickle.7z', 'rb') as infile:
        logs = pickle.load(infile)

    for key, log in logs.items():
        if args.since and args.since > key[0:8]:
            continue
        if args.before and args.before <= key[0:8]:
            continue
        gamecount += 1
        game = TenhouDecoder.Game(lang='DEFAULT', suppress_draws=False)
        game.decode(log['content'].decode())
        counter.reach_outcomes = []
        counter.addGame(game)

        for outcome in counter.reach_outcomes:
            # aggregate counter.reach_outcomes
            try:
                if outcome['type'] == 'DRAW':
                    row = 1                                  # draw
                elif outcome['points'] > 0:
                    row = 0                                  # i won
                elif outcome['points'] == -10:
                    row = 2                                  # bystander
                elif outcome['type'] == 'TSUMO':
                    row = 3                                  # lost to other's tsumo
                else:
                    row = 4                                  # dealt in

                outcomes[row][outcome['pursuit']][0] += outcome['points']
                outcomes[row][outcome['pursuit']][1] += 1

                #if outcome['pursuit']:
                reach_turn_points[row][outcome['turn']] += outcome['points']
                reach_turn_counts[row][outcome['turn']] += 1
            except:
                pass

# %% outputs

print('%d games' % gamecount)
total_hands = counter.hands['closed'] + counter.hands['opened']

print('Stats for hands won' if won_hands_only else ('Stats for all hands' if won_hands_only is None else 'Stats for hands dealt into'))
print('how, all count, all han, closed count, closed han, opened count, opened han')
if won_hands_only is None:
    print('Total hands played,%d,,%d,,%d,' % (
        total_hands,
        counter.hands['closed'],
        counter.hands['opened']))
else:
    print('%s, %d,, %d,, %d,' % (
            'Won hands' if won_hands_only else 'Hands dealt into',
            counter.relevantHands['closed'] + counter.relevantHands['opened'],
            counter.relevantHands['closed'],
            counter.relevantHands['opened']))
        
for key in counter.all.han.keys():
    print('%s, %d,%d, %d,%d, %d,%d' % (
        key,counter.all.yaku[key],counter.all.han[key],
          counter.closed.yaku[key],counter.closed.han[key],
          counter.opened.yaku[key],counter.opened.han[key],
          ))

print('\n==================================\n')

# make column totals and percentages
for pursuit in range(3):
    for row in range(5):
        for col in range(2):
            outcomes[5][pursuit][col] += outcomes[row][pursuit][col]

# print table
print('%d hands,first to riichi,,,second to riichi,,,third to riichi,,' % total_hands)
print('My outcome,My point change,hands,% of hands,My point change,hands,% of hands,My point change,hands,% of hands')
for row in range(6):
    print(outcome_names[row], end='')
    for pursuit in range(3):
        if outcomes[row][pursuit][1]:
            print(
                ',%d,%d,%d%%' % (
                    int(100 * outcomes[row][pursuit][0] / outcomes[row][pursuit][1]),
                    outcomes[row][pursuit][1],
                    int(100 * outcomes[row][pursuit][1] / outcomes[5][pursuit][1])
                ), end=''
            )
        else:
            print(',0,0,0', end='')
    print('')

print('Riichi rate,,,%.1f%%,,,%.1f%%,,,%.1f%%' % (
        100 * outcomes[5][0][1] / total_hands,
        100 * outcomes[5][1][1] / total_hands,
        100 * outcomes[5][2][1] / total_hands,
        ))


print('\n==================================\n')

print('Results by hand outcome, by turn I riichid on')
print('Turn: , ' +  ','.join(map(str, range(1, TURNS))))

for row in range(5):
    print('No. of hands - ' + outcome_names[row] + ' , ' + ','.join(map(str, reach_turn_counts[row][1:])))
    print('Points per hand - ' + outcome_names[row], end='')
    for turn in range(1, TURNS):
        if reach_turn_points[row][turn] == 0:
            print(',0',end='')
        else:
            print(',' + str(100 * reach_turn_points[row][turn] // reach_turn_counts[row][turn]), end='')
    print('')

print('average points: ', end='')
for turn in range(1, TURNS):
    nHands = 0
    points = 0
    for row in range(5):
        nHands += reach_turn_counts[row][turn]
        points += reach_turn_points[row][turn]
    if nHands == 0:
        print(',0', end='')
    else:
        print(',', str(100 * points // nHands), end='')
print('')