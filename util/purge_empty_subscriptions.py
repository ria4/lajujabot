#!/usr/bin/python3

# Run this from the main folder with: util/purge_empty_subscriptions.py
# No need to activate the virtual environment

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

def purge_pickle(subscriptions_pickle_file):
    pkl = read_pickle(subscriptions_pickle_file)
    all_subs = pkl[0]["chat_data"]
    empty_keys = [k for k,v in all_subs.items() if not v]
    for k in empty_keys:
        print("Removing key %s" % k)
        del all_subs[k]
    with open(subscriptions_pickle_file, "wb") as f:
        pickle.dump(pkl[0], f)


purge_pickle("subscriptions.pickle")
