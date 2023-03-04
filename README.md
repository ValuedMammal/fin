# flask finance app
For education only. Don't use irl  

## Easily replicate this project
assuming python installed locally:  

clone the repo  
`git clone https://github.com/ValuedMammal/fin.git`  
`cd fin`  

activate virtual environment  
`python3 -m venv venv`  
`. venv/bin/activate`  

pip install requirements  
`pip install -r requirements.txt`  

* Learning tip: A python virtual environment gives you full range of the python standard library, but in a way that isolates newly installed packages from any pip-installed packages already present on the system. This allows us to work with different versions of packages across venvs without dealing with dependency conflicts. Virtual envs are made to be disposable, and not so much portable, because you can easily spin up a new one in the desired directory.

## Set up the filesystem and database
For ease and convenience, the app has been run primarily with a sqlite db, but should be compatible with any backend offering robust support for SQL. A schema is included for all the CREATE TABLE statements that can be executed manually, however the beauty of the ORM paradigm is that by mapping tables to python objects, we can eventually tell the app to produce the database schema on its own given a set of metadata that describes the tables, columns, and relationships. This process is illustrated in model.py

The project design follows a general structure that is laid out in the [flask tutorial](https://flask.palletsprojects.com/en/2.2.x/tutorial/), so do consult this as a resource along with all the documentation for Flask, Jinja, and SQLAlchemy.

All the .py files reside in the finance folder along with the web templates and static files. Below, you'll notice the database (finance.db) actually sits in an adjacent folder called instance. The \_\_init\_\_.py file is where we create the "app factory," which allows us to add additional app blueprints in separate modules that work together to form a whole experience. This isn't the only possible set up, but it is a popular one recommended by flask. We want to pay attention to how the project is organized from the beginning, so that we can manage it as things grow, easily run tests, and later assemble the pieces into one installable package if we choose.

- fin/ (top level dir, this repo)  
  - finance/
    - \_\_init\_\_.py  
    - main.py  
    - foo.py  
    - model.py  
    - schema.sql  
    - templates/
      - index.html  
      - ...  
    - static/
      - style.css  
      - script.js  
  - instance/
    - finance.db  
    - config.py  
  - tests/  
  - venv/  

When ready, we can launch the flask server locally with `flask --app finance run`. Do this while in the fin/ directory, i.e. a level up from the finance folder. In development, you'll nearly always want to run with `--debug` on, in fact I have the flask command aliased to `flask --debug` in my own shell. If all is well, we should be able to play with our application in the browser at 127.0.0.1:5000.

## Stock quote API
One major intent of the app is to use an api to look up stock market quotes, however this will take some additional configuring, like finding a market data vendor and getting set up with an api key. For now, the project includes some (non-functional) boilerplate code for precisely this purpose, though instructive nonetheless. Thank you to CS50 for the inspiration to keep iterating on this crud app.
