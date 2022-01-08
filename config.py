import json
import os
import sys

## Default Parameters
defaultConfigFile = "config.json"


## Choose between custom or default configuration file based on user input
def selectConfigFile():
    # If the user specified a -c flag with its custom config file name
    # return that file as "active config file"
    if "-c" in sys.argv:
        if len(sys.argv) > sys.argv.index('-c') + 1:
            activeConfigFile = sys.argv[sys.argv.index('-c') + 1]
            return activeConfigFile
        else:
            sys.exit("You specified a -c flag but you didn't tell me which "
                     "config file you want to use!\n"
                     "Example syntax: python main.py -c customConfig.json\n")
    # Otherwise return the "default config file" as "active config file"
    else:
        return defaultConfigFile


## Load selected config file and verify its syntax
def loadConfigFile(activeConfigFile):
    with open(activeConfigFile, 'r') as configFile:
        try:
            config = json.load(configFile)
        except:
            sys.exit("Cannot read config file correctly")
        for k,v in config.items():
            if type(v) is str and v.startswith("$"):
                try:
                    envvar = os.environ[v[1:]]
                except:
                    sys.exit("Could not import what appears to be "
                             "an environment variable in the config file.\n"
                             f"Check your {k} parameter.")
                config[k] = envvar
        return config


## Handles app configuration
def loadConfig():
    # Choose which config file to use
    activeConfigFile = selectConfigFile()
    # Check wantend config file existence
    if os.path.exists(activeConfigFile):
        # Load config file and its json schema
        config = loadConfigFile(activeConfigFile)
        # Return the data as dictionary
        return config
    # If it doesn't exist...
    else:
        # If the user specified a custom one instead,
        # let's warn him that filedoesn't exist
        sys.exit("Sorry, the config file you specified ({}) doesn't exist".
                 format(activeConfigFile))
