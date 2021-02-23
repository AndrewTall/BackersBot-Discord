# BackersBot-Discord
Discord Bot to handle Kickstarter backers.

This bot will help you assigning roles to backers.

Requisites:
* PostgreSQL database
* Mailgun account
* Python 3

# Creating the Database
You should start by creating your database. The db_structue.sql file has all the information needed to do that. After the DB is created, you'll need to dump your backers info into this database. 

While dumping the info, please take a look at the "role_id" field in the backers table. This field allows you to have different roles per backer (based on the amount pledged for example). In order to get a role ID, you can mention the role in your server preceded by a backslash (\) and Discord will give you the ID.

# Using the Bot
Like with all Discord bots, you'll need to configure a Bot in the [Discord's developer portal](https://discordapp.com/developers/docs/intro) and get a token.

Start by installing the requirements (pip install -r requirements.txt).

Bot expects settings in enviroment variables.

When everything's set you'll need to run your bot and keep it running.