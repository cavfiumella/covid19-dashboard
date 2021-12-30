
from helpers import contagions, vaccines

from argparse import ArgumentParser
import logging
from logging import getLogger
import traceback
from typing import Dict, List, Union, Optional
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly
import plotly.graph_objects as go


LOGGER = getLogger(__name__)


def read_text(path: Path, errors: str = "ignore") -> str:
    """Read text from a file.

    Parameters:
    - path
    - errors: \"strict\" to raise exceptions, \"ignore\" to log as warning

    Returns:
    - string"""

    if errors not in ["strict", "ignore"]:
        LOGGER.warning(
            f"invalid errors \"{errors}\"; falling back to \"ignore\""
        )
        errors = "ignore"

    s = ""

    try:
        with open(path) as file:
            s = file.read().strip("\n")
    except:
        if errors == "strict":
            raise
        elif errors == "ignore":
            LOGGER.warning(traceback.format_exc())

    return s


def main(data_dir: Path = Path("share/dashboard"), /):

    title = read_text(data_dir.joinpath("title.md"))
    about = read_text(data_dir.joinpath("about.md"))
    report_bug = read_text(data_dir.joinpath("report_bug.md"))

    st.set_page_config(
        page_title=title, layout="wide",
        menu_items={"About": about, "Report a bug": report_bug}
    )

# web page title and introduction

    st.title(title)
    st.markdown(read_text(data_dir.joinpath("introduction.md")))

# select area and moving average window

    area = "Italia" # default gographical area
    mov_avg_days = 7 # default days for moving average window

    st.subheader("Dati")
    cols = st.columns(3)

    # databases
    with st.spinner("Aggiornamento dati..."):
        db = contagions.Database()

    # change geographical area
    with cols[0]:
        with st.form("geographical_form"):
            st.subheader("Area")

            options = db.get_df("regional").denominazione_regione
            options = options.drop_duplicates().sort_values().tolist()
            options += ["Italia"]

            area_input = st.selectbox(
                label="Area", options=options, index=options.index(area),
                key="geographical_selectbox"
            )

            if st.form_submit_button("Conferma"):
                area = area_input

    # moving average window length
    with cols[1]:
        with st.form("window_form"):
            st.subheader("Media mobile")

            mov_avg_days_input = st.slider(
                label="Giorni", value=mov_avg_days, min_value=1, max_value=30,
                help="Selezionare il numero di giorni da usare per il calcolo "
                     "della media mobile di alcune grandezze giornaliere "
                     "riportate nei grafici a seguire.",
                key="window_slider"
            )

            if st.form_submit_button("Conferma"):
                mov_avg_days = mov_avg_days_input

    with cols[2]:
        st.empty()

# plotting function

    def plot_section(
        cols,
        lines_values: List[List[pd.Series]],
        cols_titles: Optional[List[str]] = None,
        axes_titles: Optional[List[str]] = None,
        lines_names: Optional[List[List[str]]] = None,
        lines_colors: Optional[List[List[str]]] = None,
        lines_func: Optional[List] = None
    ) -> None:
        """Parameters:
        - cols: streamlit columns
        - lines_values: values to be passed to func
        - cols_titles: columns titles
        - axes_titles: x ans y axis titles
        - lines_names: names of plots traces
        - lines_colors: colors of plots traces
        - lines_func: function to apply over lines_values to get y values"""

        for i, col in enumerate(cols):
            with col:

                # leave col empty
                if lines_values[i] == None:
                    st.empty()
                    continue

                # write col title
                if cols_titles != None:
                    st.subheader(cols_titles[i])

                # create plot
                fig = go.Figure()

                # add plot lines
                for j, values in enumerate(lines_values[i]):

                    if lines_func != None:
                        y = lines_func(values)
                    else:
                        y = values # use values as they are

                    y = y.dropna()

                    fig.add_trace(go.Scatter(
                        x=y.index, y=y,

                        name=lines_names[i][j] \
                        if lines_names != None else None,

                        marker={"color": lines_colors[i][j]} \
                        if lines_colors != None else None
                    ))

                # plot axes titles
                if axes_titles != None:
                    fig.update_layout(
                        xaxis_title=axes_titles[i][0],
                        yaxis_title=axes_titles[i][1]
                    )

                # draw plot
                st.plotly_chart(fig)

# contagions data

    st.header("Contagi")
    st.markdown(read_text(data_dir.joinpath("contagions.md")))

    df = db.get_df(
        "national" if area == "Italia" else "regional",
        area = None if area == "Italia" else area,
        parse_dates=["data"]
    ).set_index("data")

    st.subheader("Tamponi eseguiti")

    plot_section(
        cols = st.columns(2),
        lines_values = [
            [df.tamponi],
            [df.tamponi_test_molecolare, df.tamponi_test_antigenico_rapido]
        ],
        axes_titles = [[
            "data", "valore giornaliero{}".format(
                f" (media mobile a {mov_avg_days} giorni)" \
                if mov_avg_days > 1 else ""
            )
        ]]*2,
        lines_names = [[None], ["test_molecolare", "test_antigenico_rapido"]],
        lines_func = lambda x: \
        x.diff().rolling(mov_avg_days, center=True).mean()
    )

    # positives percentage over tests
    st.subheader("Tasso di positività", anchor="tasso-di-positività")

    plot_section(
        cols = st.columns(2),

        lines_values = [

            # nuovi_positivi is not a cumulative variable
            [pd.concat([df.nuovi_positivi, df.tamponi.diff()], axis=1)],

            [
                df.loc[:, [
                    "totale_positivi_test_molecolare",
                    "tamponi_test_antigenico_rapido"
                ]].diff(),

                df.loc[:, [
                    "totale_positivi_test_antigenico_rapido",
                    "tamponi_test_antigenico_rapido"
                ]].diff()
            ]
        ],

        lines_names = [[None], ["test_molecolare", "test_antigenico_rapido"]],

        lines_func = lambda x: (
            100 * x.iloc[:,0] / x.iloc[:,1]
        ).rolling(mov_avg_days, center=True).mean(),

        axes_titles = [[
            "data",
            "valore giornaliero{}".format(
                f" (media mobile a {mov_avg_days} giorni)" \
                if mov_avg_days > 1 else ""
            )
        ]]*2,
    )

    # infections
    st.subheader("Casi positivi")

    plot_section(
        cols=st.columns(2),
        lines_values = [[df.totale_positivi], None],
        axes_titles = [["data", "valore assoluto"]]*2
    )

    st.subheader("Casi positivi per gravità")

    plot_section(
        cols=st.columns(2),

        lines_values = [
            [
                df.isolamento_domiciliare, df.ricoverati_con_sintomi,
                df.terapia_intensiva
            ],
            [
                df.isolamento_domiciliare/df.totale_positivi*100,
                df.ricoverati_con_sintomi/df.totale_positivi*100,
                df.terapia_intensiva/df.totale_positivi*100
            ]
        ],

        lines_names = [[
            "isolamento_domiciliare", "ricoverati_con_sintomi",
            "terapia_intensiva"
        ]]*2,

        lines_colors = [[
            plotly.colors.qualitative.Plotly[i] for i in [0,2,1]
        ]]*2,

        axes_titles = [
            ["data", "attualmente positivi"],
            ["data", "valore relativo [%]"]
        ]
    )

    # healed and deceased
    st.subheader("Dimessi guariti e deceduti")

    plot_section(
        cols = st.columns(2),
        lines_values = [[df.dimessi_guariti, df.deceduti], None],
        axes_titles = [
            [
                "data",
                "valore giornaliero{}".format(
                    f" (media mobile a {mov_avg_days} giorni)" \
                    if mov_avg_days > 1 else ""
                )
            ],
            None
        ],
        lines_names = [["dimessi_guariti", "deceduti"], None],
        lines_func = lambda x: \
        x.diff().rolling(mov_avg_days, center=True).mean()
    )

# vaccination data

    st.header("Vaccinazioni")
    st.markdown(read_text(data_dir.joinpath("vaccines.md")))

    # database
    with st.spinner("Aggiornamento dati..."):
        db = vaccines.Database()

    # dataframes
    df = {}
    for key, use_area in {
        "doses": True, "deliveries": True, "people": False,
        "people_booster": False
    }.items():
        df[key] = db.get_df(
            key,
            area = area if area != "Italia" and use_area else None
        )

    # add total doses column
    df["doses"].insert(
        loc = df["doses"].shape[1], column = "numero_dosi",
        value = df["doses"].filter(
            [
                "prima_dose", "seconda_dose", "pregressa_infezione",
                "dose_addizionale_booster"
            ]
        ).sum(axis=1)
    )

    # rename date columns and reindex
    for key, date_col in {
        "deliveries": "data_consegna", "doses": "data_somministrazione"
    }.items():
        df[key] = df[key].rename(columns={date_col: "data"}).set_index("data")

    # make doses and people compatible in their ages
    for key in ["doses", "people"]:
        df[key].fascia_anagrafica = df[key].fascia_anagrafica.replace(
            to_replace = ["80-89", "90+"], value = "80+"
        )

    # dataframes italian translations
    names = {
        "deliveries": "consegne", "doses": "somministrazioni",
        "people": "platea", "people_booster": "platea dose booster"
    }

    # total deliveries and doses

    st.subheader("Consegne e somministrazioni")

    plot_section(
        cols = st.columns(2),
        lines_values = [
            [df[key].numero_dosi for key in ["deliveries", "doses"]],
            None
        ],
        lines_names = [[names[key] for key in ["deliveries", "doses"]], None],
        lines_func = lambda x: x.groupby("data").sum().cumsum(),
        axes_titles = [["data", "valore cumulativo"]]*2,
    )

    # temporal developing of deliveries and doses by furniture

    st.subheader("Fornitori")

    furnitures = {
        key: df[key].fornitore.drop_duplicates().sort_values().tolist()
        for key in ["deliveries", "doses"]
    }

    plot_section(
        cols = st.columns(2),
        cols_titles = [
            names[key].capitalize() for key in ["deliveries", "doses"]
        ],

        lines_values = [
            [
                df[key].loc[lambda x: x.fornitore == furniture, "numero_dosi"]
                for furniture in furnitures[key]
            ]
            for key in ["deliveries", "doses"]
        ],

        lines_names = [furnitures[key] for key in ["deliveries", "doses"]],

        lines_func = lambda x: x.groupby("data").sum(
        ).rolling(mov_avg_days, center=True).mean(),

        axes_titles = [[
            "data",
            "valore giornaliero{}".format(
                f" (media mobile a {mov_avg_days} giorni)" \
                if mov_avg_days > 1 else ""
            )
        ]]*2
    )

    # used doses temporal developing by age, gender and type

    st.subheader("Dettaglio somministrazioni")

    ages = df["doses"].fascia_anagrafica.drop_duplicates().sort_values(
    ).tolist()
    genders = ["sesso_maschile", "sesso_femminile"]

    plot_section(
        cols = st.columns(2),
        cols_titles = ["Età", "Genere"],

        lines_values = [
            [
                df["doses"].loc[
                    lambda x: x.fascia_anagrafica == age, "numero_dosi"
                ]
                for age in ages
            ],
            [df["doses"].loc[:, gender] for gender in genders]
        ],

        lines_names = [ages, genders],

        lines_func = lambda x: x.groupby("data").sum(
        ).rolling(mov_avg_days, center=True).mean(),

        axes_titles = [[
            "data",
            "valore giornaliero{}".format(
                f" (media mobile a {mov_avg_days} giorni)" \
                if mov_avg_days > 1 else ""
            )
        ]]*2
    )

    types = [
        "prima_dose", "seconda_dose", "pregressa_infezione",
        "dose_addizionale_booster"
    ]

    plot_section(
        cols = st.columns(2),
        cols_titles = ["Tipologia", None],
        lines_values = [[df["doses"].loc[:,T] for T in types], None],
        lines_names = [types, None],
        lines_func = lambda x: x.groupby("data").sum(
        ).rolling(mov_avg_days, center=True).mean(),
        axes_titles = [[
            "data",
            "valore giornaliero{}".format(
                f" (media mobile a {mov_avg_days} giorni)" \
                if mov_avg_days > 1 else ""
            )
        ]]*2
    )

    # vaccination progress by age and type

    st.subheader("Progresso somministrazioni")

    ages = df["doses"].fascia_anagrafica.drop_duplicates().sort_values(
    ).tolist()

    types = [
        "prima_dose", "seconda_dose", "pregressa_infezione",
        "dose_addizionale_booster"
    ]

    plot_section(
        cols = st.columns(2),
        cols_titles = ["Età", "Tipologia"],

        lines_values = [
            [
                df["doses"].loc[
                    lambda x: x.fascia_anagrafica == age, "numero_dosi"
                ].groupby("data").sum().cumsum() \
                / df["people"].loc[
                    lambda x: x.fascia_anagrafica == age, "totale_popolazione"
                ].sum()

                for age in ages
            ],
            [
                df["doses"].loc[:,T].groupby("data").sum().cumsum() \
                / df["people"].totale_popolazione.sum()

                for T in types
            ]
        ],

        lines_names = [ages, types],
        axes_titles = [["data", "valore pro capite"]]*2
    )


if __name__ == "__main__":

    logging.basicConfig(
        fmt="%(asctime)s %(name)s: %(message)s",
        level=logging.INFO
    )

    try:
        main()
    except Exception:
        LOGGER.critical(traceback.format_exc())
        st.error('Si è verificato un errore inatteso. Prova a ricaricare la pagina.')
