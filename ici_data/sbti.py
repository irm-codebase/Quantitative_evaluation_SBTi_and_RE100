import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from scipy import stats

from ici import ICI
from ici import PlotterICI
import graphics
import unep


class SBTi(ICI):

    MAX_N_TARGETS = 7
    TARGET_COLUMNS = ["scope", "start year",	"base year", "target year", "tco2e covered", "% scope covered",
                      "% reduction"]

    def __init__(self):
        self.index_completed = None
        self.absolute_targets = None
        self.target_s12_tco2e = None
        self.utilities_net_gen = None
        super().__init__('SBTi')

    def initialize(self):
        super(SBTi, self).initialize()
        self.index_completed = self.central[self.central['completed'] == 'yes'].index
        self.absolute_targets = self.get_sbti_absolute_targets()
        self.target_s12_tco2e = self.get_sbti_interpolated_s12()
        self.utilities_net_gen = pd.read_excel(self.PATH+"SBTi_utilities.ods", header=[0, 1], index_col=0)

    def get_sbti_absolute_targets(self):
        """
        Construct a dataframe with target data for all approved members.
        Columns: company, target scope(s), start year, base year, target year, tco2e covered (base year),
        % base year emissions covered by target (if available, otherwise 100% is assumed), % targeted reduction

        Companies with multiple targets will have multiple rows.

        :return: pd.Dataframe [index=number (not important), columns=8 assorted values]
        """
        df = pd.DataFrame()

        for company in self.index_completed:
            for n_t in range(1, self.MAX_N_TARGETS+1):
                target = pd.Series(index=["company"]+self.TARGET_COLUMNS, dtype='object')
                target['company'] = company
                for column in self.TARGET_COLUMNS:
                    value = self.ici.loc[company, column + " t%d" % n_t]
                    if pd.isnull(value):
                        if column == self.TARGET_COLUMNS[0]:
                            target = None
                            break
                        else:
                            raise ValueError("Missing target value for SBTi:", company, n_t)
                    else:
                        target[column] = value
                if target is not None:
                    df = pd.concat([df.T, target], axis=1, ignore_index=True).T
        return df

    def get_sbti_interpolated_s12(self):
        """
        Creates a dataframe with the targeted Scope 1+2 tCO2e. If a company has multiple targets, the target with the
        nearest end-year is preferred (aka "Main target"), surrounding targets are interpolated to get a trend.
        Each target is interpolated linearly, but the final combined target can become non-linear.
        See thesis chapter 4.3.3 for specifics.

        Only works for companies who joined in 2019 or earlier.
        :return: dataframe [index=companies, columns=earliest baseline year (2000)-latest end year (2050)], in tCO2e
        """
        s12_targets = self.absolute_targets.loc[self.absolute_targets["scope"].isin(["S1+2 LB", "S1+2 MB"])]
        companies = s12_targets.value_counts('company').index
        linear_s12_targets = pd.DataFrame(index=companies, columns=['scope'])
        linear_s12_targets[np.arange(s12_targets['base year'].min(), s12_targets['target year'].max()+1)] = np.nan

        for company in linear_s12_targets.index:
            targets = s12_targets[s12_targets["company"] == company].sort_values('target year')

            b_yr1 = targets.iloc[0]['base year']
            t_yr1 = targets.iloc[0]['target year']
            b_tco2e1 = targets.iloc[0]['tco2e covered']
            t_tco2e1 = self.sbti_calculate_reduction(b_tco2e1, targets.iloc[0]['% reduction'])

            years = [b_yr1, t_yr1]
            emissions = [b_tco2e1, t_tco2e1]
            if len(targets) == 2:
                b_yr2 = targets.iloc[1]['base year']
                t_yr2 = targets.iloc[1]['target year']
                b_tco2e2 = targets.iloc[1]['tco2e covered']
                if b_yr2 < b_yr1:
                    # Other target begins before most recent one
                    years = [b_yr2] + years
                    emissions = [b_tco2e2] + emissions
                if t_yr2 > t_yr1:
                    # Other target ends after most recent one
                    t_tco2e2 = self.sbti_calculate_reduction(b_tco2e2, targets.iloc[1]['% reduction'])
                    years.append(t_yr2)
                    emissions.append(t_tco2e2)
            elif len(targets) > 2:
                raise ValueError(company, "has more than 2 targets!")

            linear_s12_targets.loc[company, years[0]:years[-1]] = np.interp(np.arange(years[0], years[-1]+1, 1), years,
                                                                            emissions)
            linear_s12_targets.loc[company, "scope"] = targets.iloc[0]["scope"]

        return linear_s12_targets

    def get_sbti_targeted_s12_results(self, group, extend_targets=False, debug=False):
        """
        Obtain a dataframe with the results of S1+2 targets for a specific group of companies
        :param group: group of companies
        :param extend_targets: (True) use baseline emissions for years prior to target baselines
                               (False, Default) use NaN values for years before target baselines
        :param debug: print messages for companies missing S2 MB info (LB data used instead)
        :return: actual S1 emissions, actual S2 emissions, targeted S1+2 emissions
                 Format: [index=companies, columns= years 2015--2019], in tCO2e
        """
        years = self.years
        emissions = self.emissions
        scopes = self.target_s12_tco2e['scope']
        targets = self.target_s12_tco2e[years].copy()
        s1_result = pd.DataFrame(index=group, columns=years)
        s2_result = pd.DataFrame(index=group, columns=years)

        if extend_targets:
            # Fill with baseline/final emission values
            for company in group:
                if targets.loc[company].count() > 0:
                    base_yr = targets.loc[company].first_valid_index()
                    targets.loc[company, :base_yr] = targets.loc[company, base_yr]

        for company in group:
            scope = scopes[company]
            for year in years:
                if not pd.isnull(targets.loc[company, year]):
                    c_emissions = emissions.loc[company]
                    if scope == "S1+2 MB":
                        s1 = c_emissions["S1 " + str(year)]
                        s2 = c_emissions["S2 MB " + str(year)]
                        if pd.isnull(s2):
                            if debug:
                                print(company, "has no MB emissions in", year, ", substituted with LB emissions")
                            s2 = c_emissions["S2 LB " + str(year)]
                    elif scope == "S1+2 LB":
                        s1 = c_emissions["S1 " + str(year)]
                        s2 = c_emissions["S2 LB " + str(year)]
                    else:
                        raise ValueError("Scope is not defined", scope)
                    if pd.isnull(s1):
                        raise ValueError(company, "has null Scope 1 values in year", year)
                    s1_result.loc[company, year] = s1
                    s2_result.loc[company, year] = s2

        return s1_result, s2_result, targets.loc[s1_result.index]

    @staticmethod
    def sbti_calculate_reduction(tco2e, reduction):
        """
        Simple targeted reduction calculation.
        :param tco2e: emissions
        :param reduction:  targeted reduction
        :return:
        """
        return (1-reduction) * tco2e


class PlotterSBTi(PlotterICI):
    def __init__(self):
        super(PlotterSBTi, self).__init__()

        self.data = SBTi()
        self.name = "SBTi"

    def plot_all(self, save=False):
        self.plot_pie_membership_all(save)
        self.plot_pie_membership(save)
        self.plot_line_dates_committed_and_targets_set(save)

    @staticmethod
    def plot_pie_membership_all(save=False):
        """
        SBTi membership as of 23/02/2021
        :param save:
        :return:
        """
        labels = ['1.5°C', "Well-below 2°C", "2°C", "Committed"]
        amounts = [306, 155, 132, 612]
        colors = graphics.get_colors(labels)

        labels = [i+" ("+str(j)+")" for i, j in zip(labels, amounts)]

        plt.figure()

        _, _, autopcts = plt.pie(amounts, radius=1, autopct='%.1f%%', startangle=270, colors=colors,
                                 pctdistance=0.6, wedgeprops=dict(edgecolor='white'))
        graphics.plot_config_pie(labels=labels, autopcts=autopcts)

        if save:
            graphics.save_figure('pie_SBTi_membership_all')

    def plot_pie_membership(self, save=False):
        status = self.data.ici.status.value_counts()
        committed = status['Committed']
        targets = status['Targets Set']
        if committed+targets != len(self.data.ici.index):
            raise ValueError("SBTi: missing or invalid in 'status' column")

        qualifications = self.data.ici.qualification.value_counts()
        at_1_5 = qualifications["1.5°C"]
        at_2 = qualifications["2°C"]
        below_2 = qualifications["Well-below 2°C"]
        if at_1_5+at_2+below_2 != targets:
            raise ValueError("SBTi: Target Sets and qualifications do not match")

        labels = ['1.5°C', "Well-below 2°C", "2°C", "Committed"]
        colors = graphics.get_colors(labels)

        values = [at_1_5, below_2, at_2, committed]
        labels = [i + " (" + str(j) + ")" for i, j in zip(labels, values)]

        plt.figure()

        _, _, autopcts = plt.pie(values, radius=1, autopct='%.1f%%', startangle=270, colors=colors,
                                 pctdistance=0.6, wedgeprops=dict(edgecolor='white'))

        plt.legend(labels=labels)
        plt.tight_layout()

        plt.setp(autopcts, **{'weight': 'bold', 'fontsize': 12.5})

        plt.axis('equal')
        plt.show()
        if save:
            graphics.save_figure('pie_SBTi_membership')

    def plot_line_dates_committed_and_targets_set(self, save=False):
        ici = self.data.ici

        statuses = ['Committed', 'Targets Set']
        columns = ['date committed', 'date target update']
        styles = ['--', '-']
        plt.figure()
        for status, column, style in zip(statuses, columns, styles):
            approved = ici[ici.status == status].copy()
            approved[column] = pd.to_datetime(approved[column], format='%Y-%m-%d %H:%M:%S')
            dates = approved[column].value_counts()
            dates = dates.sort_index()

            df = pd.DataFrame(index=dates.index)
            df['cumulative'] = 0
            tmp = 0
            for index in dates.index:
                tmp += dates[index]
                df.loc[index, 'cumulative'] = tmp

            plt.plot(df.index, df['cumulative'], style, label=status, linewidth=2.5,
                     color=graphics.get_colors(status)[0])

        date_void_committed = pd.to_datetime('2019-02-23', format='%Y-%m-%d')
        plt.axvline(date_void_committed, color='#000000', linestyle='--')
        date_void_committed = pd.to_datetime('2019-03-15', format='%Y-%m-%d')
        plt.text(date_void_committed, 30, '2-year grace period', rotation=90)
        graphics.plot_config(y_label='Companies', legend=True)

        if save:
            graphics.save_figure("line_SBTi_dates_committed_and_targets_set")

    def plot_line_sbti_s12_ambition(self, central_grouping=None, qualifications=False, save=False, show_redux=False):
        targets = self.data.target_s12_tco2e.drop('scope', axis=1)
        s12_index = targets.index

        # Build groups
        evaluation_groups = []
        evaluation_names = []
        evaluation_n_sets = []
        if qualifications:
            groups = self.data.ici.loc[s12_index, 'qualification'].value_counts().index
            for group in groups:
                tmp = self.data.ici.loc[s12_index][self.data.ici.loc[s12_index, "qualification"] == group]
                evaluation_groups.append(tmp.index)
                evaluation_n_sets.append(targets.loc[tmp.index].count())
                evaluation_names.append(group)
        elif central_grouping:
            groups = self.data.central.loc[s12_index, central_grouping].value_counts().index
            for group in groups:
                tmp = self.data.central.loc[s12_index][self.data.central.loc[s12_index, central_grouping] == group]
                evaluation_groups.append(tmp.index)
                evaluation_n_sets.append(targets.loc[tmp.index].count())
                evaluation_names.append(group)
        else:
            evaluation_groups.append(targets.index)
            evaluation_names.append("")
            evaluation_n_sets.append(targets.loc[s12_index].count())

        # Fill with baseline/final emission values
        for company in s12_index:
            base_yr = targets.loc[company].first_valid_index()
            targets.loc[company, :base_yr] = targets.loc[company, base_yr]

            target_yr = targets.loc[company].last_valid_index()
            targets.loc[company, target_yr:] = targets.loc[company, target_yr]

        # plotting: target trends, with no overlaps
        for name, index, n_set in zip(evaluation_names, evaluation_groups, evaluation_n_sets):
            plt.figure()

            cumulative_targets = targets.loc[index].sum() / 10 ** 6
            ax = cumulative_targets.loc[2015:2030].plot(linewidth=3, label="Targets (extended)",
                                                        color=graphics.get_colors(['Targets']))
            x_ticks = ax.get_xticks().tolist()
            graphics.show_sample_size_xticks(ax, x_ticks, n_set.loc[x_ticks], fix=True)

            # normalized benchmarks and baselines
            norm = cumulative_targets.loc[2019]
            benchmarks = [unep.normalize(unep.get_current_policies_ghg(), 2019, norm=norm),
                          unep.normalize(unep.get_1_5_ghg(), 2019, norm=norm),
                          unep.normalize(unep.get_2_ghg(), 2019, norm=norm)]
            labels = ["CNP", "1.5°C", "2°C"]
            styles = ["--", '-.', ':']
            for i, bench in enumerate(benchmarks):
                color = graphics.COLORMAP[labels[i]]
                bench.mean().plot(linewidth=2.5, ax=ax, label=labels[i], color=color, style=styles[i])
                plt.fill_between(bench.columns, bench.iloc[0], bench.iloc[1],
                                 color=color, alpha=0.3)

            # Add extra text
            plt.axvline(2019, color='black', linestyle='--')
            plt.text(2019, cumulative_targets.loc[2019]*.6, '$n$=%d' % int(n_set.loc[2019]), rotation=90, ha='right')
            graphics.plot_config(y_label="Scope 1+2 ($MtCO_2e$)", legend=True)

            if show_redux:
                print(name, "2015:", cumulative_targets.loc[2015],
                      "2030:", cumulative_targets.loc[2030],
                      "reduction:", 1 - cumulative_targets.loc[2030]/cumulative_targets.loc[2015])

            if save:
                filename = "SBTi_ambition_"
                if central_grouping or qualifications:
                    graphics.save_figure(filename+name, folder="sbti_ambition")
                else:
                    graphics.save_figure(filename+"all", folder="sbti_ambition")

    def plot_bar_sbti_s12_robustness(self, index=None, save=False, stacked=False, central_grouping=None, debug=False,
                                     show_sample=True):
        years = self.data.years
        if index is None:
            index = self.data.target_s12_tco2e.index
            targets = self.data.target_s12_tco2e[years]
            for i in index:  # Remove companies with empty info
                if targets.loc[i].count() == 0:
                    index = index.drop(i)
            targets = targets.loc[index]
        else:
            targets = pd.DataFrame(columns=years)

        if central_grouping:
            groups, names, n_sets = self.get_central_grouping(index, central_grouping, n_set_df=targets)
        else:
            groups = [index]
            names = [""]
            n_sets = [targets.count()]

        ver_types = ['None', 'Limited', 'Moderate', 'Reasonable', 'High']
        colors = graphics.get_color_scale('viridis', range(len(ver_types)))
        for group, name, n_set in zip(groups, names, n_sets):
            if debug:
                print(name)
            verification = self.data.verification.loc[group]
            fig, ax = plt.subplots(2)
            for i, s in enumerate(['s1', 's2']):
                scope = pd.DataFrame(index=ver_types)
                for year in years:
                    tmp = verification[year][s]
                    scope[year] = tmp.value_counts()
                if stacked:
                    tmp = scope.T.plot.bar(ax=ax[i], rot=0, legend=False, stacked=True, color=colors)
                else:
                    tmp = scope.plot.bar(ax=ax[i], rot=0, legend=False, stacked=False, color=colors)
                ax[i].yaxis.set_major_locator(graphics.mticker.MaxNLocator(integer=True))
                tmp.set_title("Scope %d" % (i+1), fontweight='bold')
                tmp.set_ylabel('Companies', fontweight='bold')
                if show_sample:
                    graphics.show_sample_size_xticks(ax[i], years, n_set)
            handles, labels = ax[0].get_legend_handles_labels()
            fig.legend(handles=reversed(handles), labels=reversed(labels), bbox_to_anchor=(0.88, 0.5), loc='center')
            fig.tight_layout(rect=[0, 0, 0.78, 1])

            if save:
                filename = "SBTi_robustness_"
                if central_grouping:
                    graphics.save_figure(filename+name, folder="sbti_robustness")
                else:
                    graphics.save_figure(filename+"all", folder="sbti_robustness")

    def plot_line_sbti_s12_implementation_users_tco2e(self, index=None, central_grouping=None, save=False, debug=False,
                                                      y_max=None, show_sample=True):
        years = self.data.years
        if index is None:
            index = self.data.remove_utilities_in_index(self.data.target_s12_tco2e.index)
            targets = self.data.target_s12_tco2e.loc[index, years]
        else:
            targets = pd.DataFrame(columns=years)

        if central_grouping:
            groups, names, n_sets = self.get_central_grouping(index, central_grouping, n_set_df=targets)
        else:
            groups = [index]
            names = [""]
            n_sets = [targets.count()]

        for group, name, n_set in zip(groups, names, n_sets):
            ax = self.plot_energy(group)
            if y_max:
                ax.set_ylim(top=y_max)
            if show_sample:
                graphics.show_sample_size_xticks(ax, years, n_set, fix=True)
            graphics.plot_config()
            if save:
                filename = "SBTi_implementation_user_"
                if central_grouping:
                    graphics.save_figure(filename + name, folder="sbti_implementation")
                else:
                    graphics.save_figure(filename + "all", folder="sbti_implementation")

    def plot_line_sbti_s12_implementation_producers_tco2e(self, index=None, save=False, debug=False, show_sample=True):
        if index is None:
            index = self.data.target_s12_tco2e.index
            index = self.data.central.loc[index][self.data.central.loc[index, 'gics sector'] == 'Utilities'].index
        utilities = self.data.utilities_net_gen.loc[index]
        total = utilities.groupby(level=[1], axis=1).sum().sum()
        years = list(range(2017, 2020))

        _, ax = plt.subplots()
        ax.set_ylim(max(total) - max(total) * 1.025, max(total) * 1.025)
        previous = pd.Series(data=0, index=years)
        markers = []
        for c in utilities.columns.levels[0]:
            color = graphics.get_colors(c)
            twh = utilities[c].sum().loc[years]
            if debug:
                print(c, twh, "total", twh/total)
            tmp = previous + twh
            plt.fill_between(years, previous, tmp, facecolor=color)
            previous = tmp
            markers = [mlines.Line2D([], [], color=color[0], label=c, linewidth=3)] + markers

        plt.legend(handles=markers, bbox_to_anchor=(1.2, 0.5), loc='center', ncol=1, borderaxespad=0.1, fancybox=True)
        if show_sample:
            graphics.show_sample_size_xticks(ax, years, self.data.target_s12_tco2e.loc[index, years].count(), fix=True)
        graphics.plot_config(y_label="TWh", int_xticks=True)

        if save:
            filename = "SBTi_implementation_producer_"
            graphics.save_figure(filename + "all", folder="sbti_implementation")

    def plot_line_sbti_s12_substantive_tco2e(self, index=None, central_grouping=None, save=False, extend=False,
                                             magnitude=10**6, y_max=None):
        if index is None:
            index = self.data.target_s12_tco2e.index
        years = self.data.years
        targets = self.data.target_s12_tco2e.loc[index, years]

        if central_grouping:
            groups, names, n_sets = self.get_central_grouping(index, central_grouping, n_set_df=targets)
        else:
            groups = [index]
            names = []
            n_sets = [targets.count()]

        for i, group in enumerate(groups):
            if extend:
                s1, s2, targets = self.data.get_sbti_targeted_s12_results(group, extend_targets=True)
                t_sub_label = " (extended)"
                r_sub_label = ""
            else:
                s1, s2, targets = self.data.get_sbti_targeted_s12_results(group)
                t_sub_label = ""
                r_sub_label = " (active)"
            s1 = (s1 / magnitude).astype('float64')
            s2 = (s2 / magnitude).astype('float64')
            results = s1 + s2
            targets = targets / magnitude

            fig, ax = plt.subplots()
            targets.loc[group].sum().plot(ax=ax, style='o-', label="Targets"+t_sub_label, lw=2.5,
                                          color=graphics.get_colors("Targets"))
            results.sum().plot(ax=ax, style='s-', label="Achieved"+r_sub_label, lw=2.5,
                               color=graphics.get_colors('Achieved'))

            plt.fill_between(years, s1.sum(), color=graphics.get_colors('Scope 1'), alpha=0.8)
            plt.fill_between(years, s1.sum(), s1.sum() + s2.sum(), color=graphics.get_colors('Scope 2'), alpha=0.8)
            s1_mkr = mlines.Line2D([], [], color=graphics.get_colors('Scope 1')[0], alpha=0.8, label="Scope 1",
                                   linewidth=3)
            s2_mkr = mlines.Line2D([], [], color=graphics.get_colors('Scope 2')[0], alpha=0.8, label="Scope 2",
                                   linewidth=3)

            if y_max:
                ax.set_ylim(top=y_max)

            handles, labels = ax.get_legend_handles_labels()
            fig.legend(handles=handles+[s2_mkr, s1_mkr], labels=labels+["Scope 2", "Scope 1"], fancybox=True, ncol=1,
                       bbox_to_anchor=(1.005, 0.5), loc='right')
            graphics.show_sample_size_xticks(ax, years, n_sets[i], fix=True)
            graphics.plot_config(y_label="Scope 1+2 ($MtCO_2e$)")
            fig.tight_layout(rect=[0, 0, 0.7, 1])

            if save:
                filename = "SBTi_substantive_"
                if extend:
                    filename += "ex_"
                if central_grouping:
                    graphics.save_figure(filename + names[i], folder="sbti_substantive")
                else:
                    graphics.save_figure(filename + "all", folder="sbti_substantive")

    def plot_bar_sbti_s12_substantive_tco2e(self, index=None, central_grouping=None, extend=False):
        if index is None:
            index = self.data.target_s12_tco2e.index
        years = self.data.years
        targets = self.data.target_s12_tco2e.loc[index, years]

        if central_grouping:
            groups, names, n_sets = self.get_central_grouping(index, central_grouping, n_set_df=targets)
        else:
            groups = [index]
            names = [""]
            n_sets = [targets.count()]

        for i, group in enumerate(groups):
            s1, s2, targets = self.data.get_sbti_targeted_s12_results(group, extend_targets=extend)
            results = s1 + s2 <= targets
            results = results.mask(targets.isna())

            evaluation = pd.DataFrame(index=years)
            evaluation['On track'] = results.sum()
            evaluation['Not on track'] = targets.count() - results.sum()

            fig, ax = plt.subplots()
            evaluation.plot.bar(ax=ax, rot=0, stacked=True, color=graphics.get_colors(evaluation.columns))
            graphics.show_sample_size_xticks(ax, years, n_sets[i])
            graphics.plot_config(title=names[i], y_label="Companies", legend=True, legend_reverse=True, int_yticks=True)
            labels = [evaluation[c].values.tolist() for c in evaluation.columns]
            for j, l in enumerate(labels):
                for h, v in enumerate(l):
                    labels[j][h] = '' if v == 0 else int(labels[j][h])

            for c, label in zip(ax.containers, labels):
                ax.bar_label(c, labels=label, label_type='center', fontweight='bold')

    def plot_pie_sbti_s12_target_groups(self, save=False):
        completed = self.data.index_completed
        ici = self.data.ici.loc[completed]
        committed = ici[ici['status'] == 'Committed'].index

        s12_absolute_index = self.data.target_s12_tco2e.index
        s12_intensity_index = completed[~completed.isin(s12_absolute_index)]
        s12_intensity_index = s12_intensity_index[~s12_intensity_index.isin(committed)]
        missing = self.data.central.index
        missing = missing[~missing.isin(completed)]

        count1 = [len(s12_absolute_index), len(s12_intensity_index), len(committed), len(missing)]
        colors1 = ['Absolute', 'Intensity/Other', 'Committed', "Missing"]
        labels1 = [c + ' (' + str(i) + ')' for i, c in zip(count1, colors1)]

        absolute = self.data.target_s12_tco2e['scope'].value_counts()
        count2 = absolute.values
        labels2 = [c + ' (' + str(i) + ')' for i, c in zip(count2, absolute.index)]

        graphics.compound_pie(count1, labels1, colors1, count2, labels2, colors1,
                              title1="Company groups", title2="Scope 1+2")
        if save:
            graphics.save_figure("pie_SBTi_s12_target_groups")

    def plot_line_pfizer_s12_target(self, save=False):
        s12 = self.data.target_s12_tco2e.loc['Pfizer'].drop('scope') / 10**6
        _, ax = plt.subplots()
        s12.plot(lw=2.5, label="Pfizer targets", color=graphics.get_colors('Targets'))
        graphics.plot_config(y_label="Scope 1+2 LB ($MtCO_2e$)", legend=True)
        ax.axvspan(2012, 2020, alpha=0.35, color='#0072B2')
        plt.text(2013, s12.loc[2012]*1.2, "Main target", rotation=90, ha='left')
        if save:
            graphics.save_figure("line_SBTi_s12_Pfizer")

    def target_sbti_stats(self, central_grouping=None, descriptive=True, magnitude=10**6):
        years = self.data.years
        absolute = self.data.target_s12_tco2e.drop("Vodafone Group").index
        abs_s1, abs_s2, _ = self.data.get_sbti_targeted_s12_results(absolute, extend_targets=True)

        intensity = self.data.ici[self.data.ici['status'] == "Targets Set"].drop(self.data.target_s12_tco2e.index).index
        intensity = intensity.drop('América Móvil')
        int_s2 = self.data.get_emissions_s2().loc[intensity]
        int_s1 = self.data.get_emissions_s1_s2().loc[intensity] - int_s2

        s1 = abs_s1.append(int_s1)
        s2 = abs_s2.append(int_s2)
        s1 = s1 / magnitude
        s2 = s2 / magnitude
        s12 = s1+s2

        if central_grouping:
            groups, names, _ = self.get_central_grouping(s12.index, central_column=central_grouping)
        else:
            groups = [s12.index]
            names = ['Total']

        for group, name in zip(groups, names):

            if descriptive:
                print(name, "2015", '-', '-', '-', '2019', "-", "-", "-", sep='\t')
                print("Scope", 'mean', 'median', 'min', 'max', 'mean', 'median', 'min', 'max', sep='\t')
                for scope, scope_name in zip([s1, s2, s12], ['S1', 'S2', 'S1+2']):
                    tmp = scope.loc[group]
                    maxi = [round(i, 3) for i in tmp.max()]
                    mini = [round(i, 3) for i in tmp.min()]
                    mean = [round(i, 3) for i in tmp.mean()]
                    median = [round(i, 3) for i in tmp.median()]
                    n = tmp.count()[2015]

                    print(scope_name, mean[0], median[0], mini[0], maxi[0], mean[-1], median[-1], mini[-1], maxi[-1],
                          n)

            else:
                print(name)
                print("Scope", "companies", "2015", "2019", "AAGR", "$R^2$", "$p$", "std_err", sep='\t')
                for scope, scope_name in zip([s1, s2, s12], ['S1', 'S2', 'S1+2']):
                    tmp = scope.loc[group].sum()
                    aagr = self.data.calculate_aagr(tmp.values)
                    slope, intercept, r_value, p_value, std_err = stats.linregress(years, tmp.values.tolist(),
                                                                                   alternative="less")
                    print(scope_name, len(group), round(tmp[2015], 3), round(tmp[2019], 3), str(round(aagr*100, 3))+'%',
                          round(r_value**2, 3), round(p_value, 3), round(std_err, 3), sep='\t')

    def thesis(self, save=False):
        self.plot_pie_membership_all(save)
        self.plot_pie_membership(save)
        self.plot_line_dates_committed_and_targets_set(save)
        self.plot_pie_sbti_s12_target_groups(save)
        self.plot_line_pfizer_s12_target(save=save)
        # ambition
        self.plot_line_sbti_s12_ambition(save=save)
        self.plot_line_sbti_s12_ambition(save=save, central_grouping='energy sector')
        self.plot_line_sbti_s12_ambition(save=save, central_grouping='gics sector')
        self.plot_line_sbti_s12_ambition(save=save, qualifications=True)
        # robustness
        self.plot_bar_sbti_s12_robustness(save=save, stacked=True)
        self.plot_bar_sbti_s12_robustness(save=save, central_grouping="energy sector", stacked=True)
        self.plot_bar_sbti_s12_robustness(save=save, central_grouping="gics sector", stacked=True)
        # implementation
        self.plot_line_sbti_s12_implementation_producers_tco2e(save=save)
        self.plot_line_sbti_s12_implementation_users_tco2e(save=save)
        self.plot_line_sbti_s12_implementation_users_tco2e(save=save, central_grouping='energy sector', y_max=290)
        self.plot_line_sbti_s12_implementation_users_tco2e(save=save, central_grouping='gics sector')
        # substantive
        self.plot_line_sbti_s12_substantive_tco2e(extend=False, save=save)
        self.plot_line_sbti_s12_substantive_tco2e(extend=True, save=save)
        self.plot_line_sbti_s12_substantive_tco2e(central_grouping='energy sector', extend=True, save=save, y_max=133)
        self.plot_line_sbti_s12_substantive_tco2e(central_grouping='gics sector', extend=True, save=save)
        # early members
        early_targets = self.data.target_s12_tco2e.loc[:, 2015:2017].count(axis=1)
        late_members = early_targets[early_targets == 0].index
        self.plot_line_sbti_s12_substantive_tco2e(index=late_members, extend=True)
        if save:
            graphics.save_figure("SBTi_substantive_ex_recent_targets", folder="sbti_substantive")
        self.plot_bar_sbti_s12_substantive_tco2e(index=late_members, extend=True)
        if save:
            graphics.save_figure("SBTi_substantive_bar_recent_targets", folder="sbti_substantive")
        self.plot_pie_by_central(self.data.target_s12_tco2e.index)
        if save:
            graphics.save_figure("SBTi_absolute_pie")
        self.plot_line_s12_by_sector(self.data.target_s12_tco2e.index.drop("Vodafone Group"), legend=True)
        if save:
            graphics.save_figure("SBTi_absolute_line_sector")

    def intensity(self, save=False):
        folder = 'sbti_other_targets'
        intensity = self.data.ici[self.data.ici['status'] == "Targets Set"].drop(self.data.target_s12_tco2e.index).index
        intensity = intensity.drop('América Móvil')
        self.plot_line_s12_by_sector(intensity, legend=False)
        graphics.save_figure("SBTi_int_sector_tco2", folder=folder)
        self.plot_pie_by_central(intensity, startangle=20)
        graphics.save_figure("SBTi_int_sector_pie", folder=folder)
        self.plot_line_sbti_s12_implementation_producers_tco2e(index=['Enel', 'Engie'], show_sample=False)
        graphics.save_figure("SBTi_int_sector_utilities", folder=folder)
        self.plot_line_sbti_s12_implementation_users_tco2e(index=["LafargeHolcim"], show_sample=False)
        graphics.save_figure("SBTi_int_LafargeHolcim", folder=folder)
        self.plot_bar_sbti_s12_robustness(index=intensity, show_sample=False, stacked=True)
        graphics.save_figure("SBTi_int_robustness", folder=folder)

    def committed(self):
        folder = 'sbti_other_targets'
        missing = ["CMA CGM", "Amazon", "Volvo", "X5 Retail Group", "Phoenix Group Holdings", "Fubon Financial Holding"]
        excluded = ['Starbucks', 'Adidas', 'Migros Group', 'Linde', 'Sumitomo Electric Industries', 'BMW',
                    'Facebook', 'Ford Motor', 'General Motors', 'Banco do Brasil', 'Credit Suisse Group']
        committed = self.data.ici[self.data.ici['status'] == "Committed"].index
        committed = committed.drop(excluded+missing)
        print(self.data.central.loc[committed, "energy sector"])
        self.plot_line_s12_by_sector(committed, legend=False)
        graphics.save_figure("SBTi_committed_sector_tco2", folder=folder)
        self.plot_pie_by_central(committed)
        graphics.save_figure("SBTi_committed_sector_pie", folder=folder)

    def discussion(self, save=False):
        # Building index
        folder = 'sbti_discussion'
        absolute = self.data.target_s12_tco2e.drop("Vodafone Group").index
        intensity = self.data.ici[self.data.ici['status'] == "Targets Set"].drop(self.data.target_s12_tco2e.index).index
        intensity = intensity.drop('América Móvil')
        tmp = self.data.central.loc[absolute.append(intensity)]
        internal_change_sectors = ['Electricity Generation']
        index = tmp[~tmp["energy sector"].isin(internal_change_sectors)].index

        self.plot_implementation_market_instruments(index, save=save, folder=folder)

        self.plot_implementation_market_instruments(index, plot_area=True, save=save, folder=folder, legend=True)

    def log_frame(self, save=False, sector=None):
        self.plot_line_sbti_s12_ambition(save=save, central_grouping=sector)
        if sector is None:
            self.plot_bar_sbti_s12_robustness(stacked=True)
        self.plot_line_sbti_s12_implementation_users_tco2e()
        self.plot_line_sbti_s12_substantive_tco2e()
        self.plot_line_sbti_s12_substantive_tco2e(extend=True)
        # self.plot_bar_sbti_s12_substantive_tco2e()
        self.plot_line_sbti_s12_substantive_tco2e(extend=False, save=True)
        self.plot_line_sbti_s12_substantive_tco2e(extend=True, save=True)
        self.plot_line_sbti_s12_substantive_tco2e(central_grouping='energy sector', extend=True, save=True)
        self.plot_line_sbti_s12_substantive_tco2e(central_grouping='gics sector', extend=True, save=True)

# #
# tst = PlotterSBTi()
# tst.plot_line_sbti_s12_substantive_tco2e(extend=True)
