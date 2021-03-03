#!/usr/bin/python3

import pickle


def read_pickle(pickle_file):
    objects = []
    with open(pickle_file, "rb") as f:
        while True:
            try:
                objects.append(pickle.load(f))
            except EOFError:
                break
    return objects

def print_pickle(subscriptions_pickle_file):
    all_subs = read_pickle(subscriptions_pickle_file)[0]["chat_data"]
    for chat_id, user_subs in all_subs.items():
        print(chat_id)
        for channel_name in user_subs.values():
            print("\t%s" % channel_name)
        print()

print_pickle("subscriptions.pickle")
