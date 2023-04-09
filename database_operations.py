import pandas as pd


def move_column(dataframe, moved_name, position_name):
    """
    Moves a dataframe column to the position of another, preserving dataframe integrity
    :param pd.DataFrame dataframe:
    :param str moved_name: name of the column to be re-arranged
    :param str position_name: name of the column were it will be placed
    :return pd.DataFrame dataframe: return the re-arranged dataframe
    """
    columns = dataframe.columns.to_list()
    columns.insert(columns.index(position_name), columns.pop(columns.index(moved_name)))
    return dataframe.reindex(columns=columns)


def add_column(dataframe, series, column_name, position_name=None):
    """
    Adds a series as a dataframe column, with the option to specify the position where it'll be added.
    Indexes must be the same between dataframe and series.
    :param pd.DataFrame dataframe:
    :param pd.Series series: Series to be added. Indexes must match.
    :param str column_name: name of the added column
    :param position_name: name of the column where the new column will be placed (old one will shift to the right)
    :return: pd.Dataframe
    """
    dataframe[column_name] = series
    if position_name is not None:
        dataframe = move_column(dataframe, column_name, position_name)
    return dataframe


def flatten_multi_columns(dataframe, separator='|'):
    """
    Flattens columns of a Multi Index dataframe, keeping the column names of both levels, separating them by a symbol.
    :param  pd.DataFrame dataframe: Multi Index dataframe to be flattened
    :param str separator: index name separator. e.g. "top name|sub name"
    :return:
    """
    dataframe.columns = dataframe.columns.map('|'.join)
    return dataframe
