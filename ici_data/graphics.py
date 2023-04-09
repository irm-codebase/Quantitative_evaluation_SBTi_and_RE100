import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib import cm
from matplotlib import colors
from collections.abc import Iterable
from matplotlib.patches import ConnectionPatch
import matplotlib.lines as mlines
import numpy as np
import string
from itertools import cycle

plt.style.use('ggplot')
plt.rcParams['axes.grid'] = True
plt.rcParams['font.size'] = '10'

# Taken from https://htmlcolorcodes.com/
# Initiatives are 8th row with 1 spacing
# Electricity instruments are 5th row with 1 spacing
COLORMAP = {'G500': "#D55E00", 'Both': "#CC79A7", 'SBTi': "#0072B2", 'RE100': "#009E73", 'ICI': 'grey',
            'U-EACs': "#DC7633", 'Utility GPs': "#F5B041", 'PPAs': '#58D68D',
            'Self-gen Elec': "#45B39D", "RE Fuel": "#56B4E9", "Unknown": "#777777",
            '1.5°C': "#56B4E9", 'Well-below 2°C': "#F0E442", '2°C': "#CC79A7", "Committed": 'grey',
            'CNP': 'grey', "On track": '#56B4E9', "Not on track": '#D55E00',
            'Targets': '#E69F00', 'Achieved': '#0072B2',
            'Targets Set': '#E69F00',
            'Absolute': "#E69F00", "Intensity/Other": "#009E73", "Missing": "#D55E00",
            'Fossil': "#D55E00", 'Renewable': "#009E73", "Nuclear": "#0072B2",
            'Scope 1': "#56B4E9", "Scope 2": "#F0E442",
            'Light Industry': '#E69F00', 'Services': "#56B4E9", 'Electricity Generation': "#009E73",
            'Energy Intensive Industry': "#F0E442", 'Transport': "#0072B2", "Fossil Fuel Production": "#D55E00",
            "All indicators": "#E69F00", "Only ambition": "#56B4E9", "None": "grey",
            "Total": "#D55E00",
            "SSP1-1.5 OECD": "#56B4E9", "SSP2-Base OECD": 'grey',
            "Financials": "#E69F00", "Consumer Discretionary": "#56B4E9", "Consumer Staples": "#009E73",
            "Information Technology": "#F0E442", "Communication Services": "#0072B2", "Industrials": "#D55E00",
            "Health Care": "#CC79A7", "Real Estate": "#777777"}

COLORBLIND = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#777777"]

EU_28 = ['Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus', 'Czechia', 'Denmark', 'Estonia', 'Finland',
         'France', 'Germany', 'Greece', 'Hungary', 'Ireland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta',
         'Netherlands', 'Poland', 'Portugal', 'Romania', 'Slovakia', 'Slovenia', 'Spain', 'Sweden', 'U.K.']


def plot_config(title=None, y_label=None, x_label=None, int_xticks=False, int_yticks=False, y_ax_percent=False,
                x_ax_percent=False, legend=False, legend_loc='best', legend_reverse=False, ax=None):
    """
    Generic plot configurator. Not recommended, kept for compatibility with some plots in the thesis.
    :param title:
    :param y_label:
    :param x_label:
    :param int_xticks:
    :param int_yticks:
    :param y_ax_percent:
    :param x_ax_percent:
    :param legend:
    :param legend_loc:
    :param legend_reverse:
    :param ax:
    :return:
    """
    if ax is None:
        ax = plt.gca()
    if title:
        plt.title(title, fontweight='bold')
    if x_label:
        ax.set_xlabel(x_label, fontweight='bold')
    if y_label:
        ax.set_ylabel(y_label, fontweight='bold')
    if legend:
        if legend_reverse:
            handles, labels = ax.get_legend_handles_labels()
            ax.legend(reversed(handles), reversed(labels), loc=legend_loc)
        else:
            ax.legend(loc=legend_loc)
    if int_xticks:
        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    if int_yticks:
        ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    if y_ax_percent:
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
        ax.set_ylim([-0.05, 1.05])
    if x_ax_percent:
        ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
        ax.set_xlim([-0.05, 1.05])

    plt.tight_layout()


def plot_config_pie(title=None, labels=None, autopcts=None, fontsize=12.5):
    if title:
        plt.title(title, fontweight='bold')
    if labels:
        plt.legend(labels=labels)
    if autopcts:
        plt.setp(autopcts, **{'weight': 'bold', 'fontsize': fontsize})

    plt.tight_layout()
    plt.axis('equal')


def get_color_scale(name, values):
    """
    Produces color scale using a default matplotlib color map.
    :param name: name of the matplotlib color map to use
    :param values: list of values to scale. Min/max values are used to determine the range of the scale
    :return:
    """
    cmap = cm.get_cmap(name)
    mini = min(values)
    maxi = max(values)
    norm = colors.Normalize(vmin=mini, vmax=maxi)
    color_scale = [cmap(norm(value)) for value in values]
    return color_scale


def save_figure(name, folder=None):
    """
    Saves the current active figure. Legacy code and not recommended.
    :param name:
    :param folder:
    :return:
    """
    fig_path = '/home/ivan/Documents/GitHub/G500_database/figures/'
    thesis_path = '/home/ivan/Documents/GitHub/Thesis/src/python images/'
    if folder:
        fig_path += folder+'/'
        thesis_path += folder+'/'
    plt.savefig(fig_path+name+'.pdf')
    plt.savefig(thesis_path+name+'.pdf')


def get_colors(labels):
    """
    Returns the colors depending on the labels used, in order.
    :param labels: the labels in the plot
    :return:
    """
    if type(labels) == str:
        labels = [labels]
    values = []
    for key in labels:
        values.append(COLORMAP[key])
    return values


def bar(values, groups, label, color, width=0.9, barh=False, num_show=False, num_max=None):
    """
    Produces a bar plot. Legacy code and not recommended.
    :param values:
    :param groups:
    :param label:
    :param color:
    :param width:
    :param barh:
    :param num_show:
    :param num_max:
    :return:
    """
    if isinstance(values[0], Iterable):
        n = len(values)
    else:
        values = [values]
        n = 1

    x = np.arange(len(groups))
    fig, ax = plt.subplots()
    width = width / n

    for i in range(n):
        space = width*((i - n / 2) + .5)
        if barh:
            rect = ax.barh(x + space, values[i], width, label=label[i], color=color[i])
            ax.set_yticks(x)
            ax.set_yticklabels(groups)

        else:
            rect = ax.bar(x + space, values[i], width, label=label[i], color=color[i])
            ax.set_xticks(x)
            ax.set_xticklabels(groups)

        if num_show:
            if num_max:
                values[i] = [v if v < num_max else '' for v in values[i]]
            ax.bar_label(rect, values[i])


def pie(values, labels, color_names=None, color_list=None, startangle=0):
    """
    Produces a pie plot. Legacy code and not recommended.
    :param values:
    :param labels:
    :param color_names:
    :param color_list:
    :param startangle:
    :return:
    """
    plt.figure()

    if color_names:
        c = get_colors(color_names)
    else:
        c = color_list

    _, _, autopcts = plt.pie(values, radius=1, autopct='%.1f%%', startangle=startangle, colors=c,
                             pctdistance=0.6, wedgeprops=dict(edgecolor='white'))

    plt.legend(labels=labels)
    plot_config_pie(labels=labels, autopcts=autopcts)


def compound_pie(values1, labels1, colors1, values2, labels2, colors2, title1=None, title2=None):
    """
    Produces a compound pie plot. Legacy code, and not recommended.
    :param values1:
    :param labels1:
    :param colors1:
    :param values2:
    :param labels2:
    :param colors2:
    :param title1:
    :param title2:
    :return:
    """
    # make figure and assign axis objects
    fig = plt.figure(figsize=(9, 5.0625))
    ax1 = fig.add_subplot(121)
    ax2 = fig.add_subplot(122)
    fig.subplots_adjust(wspace=0)
    explode = np.zeros(len(values1))
    explode[0] = 0.1
    # large pie chart parameters
    # rotate so that first wedge is split by the x-axis
    angle = -values1[0]/(2*sum(values1)) * 360
    ax1.pie(values1, autopct='%1.1f%%', startangle=angle, colors=get_colors(colors1),
            labels=labels1, explode=explode)

    # small pie chart parameters
    width = .2

    ax2.pie(values2, autopct='%1.1f%%', startangle=angle, colors=get_colors(colors2),
            labels=labels2, radius=0.5, textprops={'size': 'smaller'})

    if title1:
        ax1.set_title(title1)
    if title2:
        ax2.set_title(title2)

    # use ConnectionPatch to draw lines between the two plots
    # get the wedge data
    theta1, theta2 = ax1.patches[0].theta1, ax1.patches[0].theta2
    center, r = ax1.patches[0].center, ax1.patches[0].r

    # draw top connecting line
    x = r * np.cos(np.pi / 180 * theta2) + center[0]
    y = np.sin(np.pi / 180 * theta2) + center[1]
    con = ConnectionPatch(xyA=(- width / 2, .5), xyB=(x, y),
                          coordsA="data", coordsB="data", axesA=ax2, axesB=ax1)
    con.set_color([0, 0, 0])
    con.set_linewidth(2)
    ax2.add_artist(con)

    # draw bottom connecting line
    x = r * np.cos(np.pi / 180 * theta1) + center[0]
    y = np.sin(np.pi / 180 * theta1) + center[1]
    con = ConnectionPatch(xyA=(- width / 2, -.5), xyB=(x, y), coordsA="data",
                          coordsB="data", axesA=ax2, axesB=ax1)
    con.set_color([0, 0, 0])
    ax2.add_artist(con)
    con.set_linewidth(2)
    plt.show()


def show_sample_size_xticks(ax, x_names, n_sizes, fix=False):
    if fix:
        ax.xaxis.set_major_locator(mticker.FixedLocator(x_names))
    ax.set_xticklabels(["%d\n$t$=%d" % (x, n) for x, n in zip(x_names, n_sizes)])


def legend_add_marker(ax, label, shape, color, markersize=None):
    """
    Adds makers to the legend of a plot. Legacy code, and not recommended.
    :param ax:
    :param label:
    :param shape:
    :param color:
    :param markersize:
    :return:
    """
    handles, labels = ax.get_legend_handles_labels()
    line = mlines.Line2D([], [], marker=shape, linestyle="None", color=color, label=label, markerfacecolor='none',
                         markersize=markersize)
    ax.legend(handles=handles+[line], labels=labels+[label])


def label_axes(fig, labels=None, loc=None, **kwargs):
    """
    Walks through axes and labels each.

    kwargs are collected and passed to `annotate`

    Parameters
    ----------
    fig : Figure
         Figure object to work on

    labels : iterable or None
        iterable of strings to use to label the axes.
        If None, lower case letters are used.

    loc : len=2 tuple of floats
        Where to put the label in axes-fraction units
    """
    if labels is None:
        labels = string.ascii_lowercase

    # re-use labels rather than stop labeling
    labels = cycle(labels)
    if loc is None:
        loc = (.9, .9)
    for ax, lab in zip(fig.axes, labels):
        ax.annotate(lab, xy=loc, xycoords='axes fraction', **kwargs)


def label_axis(ax, label, loc=None, **kwargs):
    """
    Walks through axes and labels each.

    kwargs are collected and passed to `annotate`

    Parameters
    ----------
    ax : Axis
         Axis object to work on

    label : string
        string to use to label the axes.

    loc : len=2 tuple of floats
        Where to put the label in axes-fraction units
    """
    if loc is None:
        loc = (.9, .9)

    ax.annotate(label, xy=loc, xycoords='axes fraction', **kwargs)
