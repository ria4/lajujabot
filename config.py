from jsonschema import validate, exceptions
import sys
import os
import json

## Default Parameters
defaultConfig = {
    'TelegramBotToken': '',
    'TwitchAppClientID': '',
    'TwitchAppClientSecret': '',
    'CallbackURL': '',
    'ListeningPort': '15151'
}
defaultConfigFile = "config.json"
configSchema = "configSchema.json"


## Choose between custom or default
## configuration file based on user input
def selectConfigFile():
    # If the user specified a -c flag with its custom config file name
    # return that file as "active config file"
    if "-c" in sys.argv:
        if len(sys.argv) > sys.argv.index('-c') + 1:
            activeConfigFile = sys.argv[sys.argv.index('-c') + 1]
            print("Using custom config file: " + activeConfigFile)
            return activeConfigFile
        else:
            sys.exit("You specified a -c flag but you didn't tell me which" +
                     "config file you want to use!\n\n" +
                     "Example syntax:\n python main.py -c customConfig.json\n")
    # Otherwise return the "default config file" as "active config file"
    else:
        return defaultConfigFile


## Creating default blank configuration file in case the user didn't create one
def createBlankConfigFile():
    with open('config.json', 'w') as blankConfigFile:
        json.dump(defaultConfig, blankConfigFile, indent=4)


## Load json schema for config file
def loadConfigSchema():
    with open('configSchema.json', 'r') as configSchemaFile:
        configSchema = json.load(configSchemaFile)
        return configSchema


## Load selected config file and verify its syntax
def loadConfigFile(activeConfigFile):
    with open(activeConfigFile, 'r') as configFile:
        try:
            config = json.load(configFile)
            return config
        except:
            sys.exit("Cannot read config file correctly")


## Validate configuration data against its json schema
def validateConfiguration(config, configSchema):
    try:
        validate(config, configSchema)
    except exceptions.ValidationError as e:
        sys.exit("Something's wrong with your config file:\n" +
                 "Instance: {}\nError: {}".format(e.path[0], e.message))


## Handles app configuration
def loadConfig():
    # Choose which config file to use
    activeConfigFile = selectConfigFile()
    # Check wantend config file existence
    if os.path.exists(activeConfigFile):
        # Load config file and its json schema
        configSchema = loadConfigSchema()
        config = loadConfigFile(activeConfigFile)
        # Validate the data and interrupt the application if the
        # data is not valid...
        validateConfiguration(config, configSchema)
        # ...or return the valid data as dictionary
        return config
    # If it doesn't exist...
    else:
        # ...and we want the default config file just create a blank one
        if activeConfigFile == defaultConfigFile:
            createBlankConfigFile()
            sys.exit("Config file not found!\n" +
                     "I've created a blank one for you")
        # If the user specified a custom one instead,
        # let's warn him that filedoesn't exist
        else:
            sys.exit("Sorry, the config file you specified ({}) doesn't exist".
                     format(activeConfigFile))
