"""Main script for dashboard webpage.

This script builds a dashboard for Covid19 contagions and vaccinations in Italy.
The project bases on Dash and Plotly libraries for UI.
"""


import logging
from logging import getLogger
from argparse import ArgumentParser
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly
import plotly.graph_objects as go
import pandas as pd


app = dash.Dash(__name__)

paths = {
    "contagions_national": "share/contagions/dati-andamento-nazionale",
    "contagions_regional": "share/contagions/dati-regioni",
    "doses": "share/vaccinations/somministrazioni-vaccini-latest.csv",
    "deliveries": "share/vaccinations/consegne-vaccini-latest.csv",
    "people": "share/vaccinations/plates.csv",
    "people_booster": "share/vaccinations/platea-dose-addizionale-booster.csv"
}

df = {key: pd.read_csv(path) for key, path in paths.items()}


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-D", "--debug", action="store_true")

    app.run_server(debug=args.debug)
