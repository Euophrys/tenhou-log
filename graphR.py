"""
display a graph of R over time
"""

# core libraries
import argparse
import lzma
import pickle
import math

# third-party libraries
import matplotlib.pyplot as plt

# own imports
from TenhouConfig import account_names, directory_name
import TenhouDecoder

parser = argparse.ArgumentParser()
parser.add_argument(
    '--sanma',
    help='Show three-player rate instead of four-player',
    action='store_true')

args = parser.parse_args()

RANKS = "10k,9k,8k,7k,6k,5k,4k,3k,2k,1k,1d,2d,3d,4d,5d,6d,7d,8d,9d,10d,Tenhoui".split(",")
HOUOU_R = 2000.0
TOKUJOU_R = 1800.0

figure_count = 1

for player in account_names:
    with lzma.open(directory_name + player + '.pickle.7z', 'rb') as infile:
        logs = pickle.load(infile)

    R_values = []
    rank_up_games = []
    rank_up_R = []
    rank_up_ranks = []
    rank_down_games = []
    rank_down_R = []
    rank_down_ranks = []
    current_rank = -1

    for key, log in logs.items():
        if log['lobby'] != 0:
            # No reason to track R outside of ranked
            continue
        if args.sanma and not '' in log['uname']:
            continue
        elif not args.sanma and '' in log['uname']:
            continue
        R_values.append(log["rate"])

        # Check for rank changes
        game = TenhouDecoder.Game(lang='DEFAULT', suppress_draws=True)
        game.decode(log['content'].decode())
        
        player_data = None
        for idx, player_object in enumerate(game.players):
            if player_object.name == player:
                player_data = player_object
                break
        
        if player_data == None:
            continue # ??

        player_rank = game.RANKS.index(player_data.rank)
        
        if current_rank != -1:
            # This is gross but plot needs the data in different arrays
            if player_rank > current_rank:
                rank_up_games.append(len(R_values))
                rank_up_ranks.append(RANKS[player_rank])
            elif player_rank < current_rank:
                rank_down_games.append(len(R_values))
                rank_down_ranks.append(RANKS[player_rank])
        
        current_rank = player_rank

    value_count = len(R_values)
    current_R = R_values[value_count - 1]

    R_threshold = HOUOU_R if current_R >= TOKUJOU_R else TOKUJOU_R

    figure = plt.figure(figure_count)
    figure_count += 1

    plt.plot([0, value_count + 2], [R_threshold, R_threshold], 'r')

    # This acts really weird with sanma games. I think the data is weird but I can't find what's wrong. Remove this if if it gets fixed.
    if not args.sanma:
        # Fetch the R values, then put text showing the ranks
        for i in range(len(rank_up_games)):
            rank_up_R.append(R_values[rank_up_games[i]])
            plt.text(rank_up_games[i], rank_up_R[i], rank_up_ranks[i], color='green', horizontalalignment='right')
        for i in range(len(rank_down_games)):
            rank_down_R.append(R_values[rank_down_games[i]])
            plt.text(rank_down_games[i], rank_down_R[i], rank_down_ranks[i], color='red', horizontalalignment='right')

        if len(rank_up_games) > 0:
            plt.plot(rank_up_games, rank_up_R, 'g^')

        if len(rank_down_games) > 0:
            plt.plot(rank_down_games, rank_down_R, 'rv')

    plt.plot(range(0, value_count), R_values, 'b')

    plt.ylabel("Rate")
    plt.xlabel("Games Played")
    plt.suptitle("%s %s Rate Over Time" % (player, "3P" if args.sanma else "4P"))

    # Add a label for the user's highest and current R
    highest_R = max(R_values)
    highest_R_game = R_values.index(highest_R)
    plt.text(highest_R_game, highest_R, '%d R' % highest_R, color='green', horizontalalignment='center')
    plt.text(value_count - 1, current_R, '%d R' % current_R, horizontalalignment='center')

plt.grid(True)
plt.show()