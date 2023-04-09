import pandas as pd
import numpy as np
from ici import ICI
from ici import PlotterICI
import graphics
import ipcc_scenarios
from graphics import plt


class RE100(ICI):

    def __init__(self):
        self.missing = None
        self.index_baseline_pre_2020 = None
        self.target_ratios = None
        self.index_analysis = None
        super().__init__('RE100')

    def initialize(self):
        super(RE100, self).initialize()
        self.missing = ["M&G", "Seven & I Holdings"]
        self.index_baseline_pre_2020 = self.get_index_baseline_pre_2020()
        self.fill_missing_baselines()
        self.target_ratios = self.get_target_ratios()
        completed = self.ici.drop(self.missing)
        self.index_analysis = completed[completed["joining year"] <= max(self.years)].index

    def fill_missing_baselines(self):
        """
        Some companies do not have baselines or are not included in the RE100 report.
        For them, fill in the info with the baseline year (joining year minus one, generally).
        :return:
        """
        missing = self.ici[self.ici.loc[:, 'baseline'].isna()]
        for company in missing.index:
            baseline_yr = missing.loc[company, "baseline year"]
            if baseline_yr < 2020:
                re_ratios = self.get_company_energy_re_electricity_ratio(company)
                baseline = re_ratios[baseline_yr]
                self.ici.loc[company, 'baseline'] = baseline

    def get_index_baseline_pre_2020(self):
        """
        Finds which companies joined before 2019
        :return: list of company names
        """
        index = self.central.drop(self.missing).index
        tmp = self.ici.loc[index, :]
        index = tmp[tmp['baseline year'] < 2020].index
        return index

    def get_target_ratios(self):
        """
        Creates a dataframe with the targeted ratio of renewable electricity per company, assuming linear target trends.
        Only works for companies who joined in 2019 or earlier
        :return: linear target ratios [index=companies, columns=2014--2050], values in %
        """
        linear_target_ratios = pd.DataFrame(index=self.index_baseline_pre_2020, columns=np.arange(2014, 2050 + 1))

        for company in self.index_baseline_pre_2020:
            baseline_yr = self.ici.loc[company, 'baseline year']
            baseline_ratio = self.ici.loc[company, 'baseline']
            final_yr = self.ici.loc[company, 'final year']

            if baseline_ratio >= 1:
                target_ratios = np.ones(2050 - int(baseline_yr) + 1)
            else:
                years = [baseline_yr]
                ratios = [baseline_ratio]

                interim_yr1 = self.ici.loc[company, 'interim year 1']
                if np.isnan(interim_yr1):
                    if final_yr == 2050:
                        years += [2030, 2040]
                        ratios += [0.6, 0.9]
                else:
                    ratio_interim1 = self.ici.loc[company, 'interim target 1']
                    if not np.isnan(ratio_interim1):
                        years.append(interim_yr1)
                        ratios.append(ratio_interim1)
                        interim_yr2 = self.ici.loc[company, 'interim year 2']
                        if not np.isnan(interim_yr2):
                            ratio_interim2 = self.ici.loc[company, 'interim target 2']
                            if not np.isnan(ratio_interim2):
                                years.append(interim_yr2)
                                ratios.append(ratio_interim2)
                    else:
                        raise ValueError("Missing interim target", company)
                years.append(final_yr)
                ratios.append(1)
                if final_yr != 2050:
                    years.append(2050)
                    ratios.append(1)

                target_ratios = np.interp(np.arange(baseline_yr, 2050 + 1, 1), years, ratios)

            linear_target_ratios.loc[company, baseline_yr:] = target_ratios

        return linear_target_ratios

    def get_baseline_total_electricity_extended(self):
        """
        Returns a dataframe filled with the electricity consumed in the target baseline year of a company.
        This value is kept constant for subsequent years, up to 2050.
        For a few companies with their baseline in 2014, the 2015 value is used instead.
        Years before target baselines have NaN values.
        :return: pandas.Dataframe [index=companies, columns=2015--2050], values in MWh
        """
        index = self.index_baseline_pre_2020
        baseline_electricity = pd.DataFrame(index=index, columns=np.arange(2014, 2050 + 1))
        baseline_years = self.ici.loc[index, 'baseline year']
        electricity = self.total_electricity.loc[index]
        for company in index:
            year = baseline_years[company]
            if year == 2014:
                baseline_electricity.loc[company, year:] = electricity.loc[company, 2015]
            else:
                baseline_electricity.loc[company, year:] = electricity.loc[company, year]

        return baseline_electricity

    def get_baseline_targeted_re_electricity_extended(self):
        """
        Returns a dataframe filled with the targeted renewable electricity consumption assuming baseline consumption
        remains constant.
        Years before target baselines have NaN values.
        :return: pandas.Dataframe [index=companies, columns=2015--2050], values in MWh
        """
        baseline_electricity = self.get_baseline_total_electricity_extended()
        ratios = self.target_ratios
        return baseline_electricity * ratios

    def get_re100_targeted_results(self, group, extend_targets=False):
        """
        Obtain dataframes with the results of S1+2 targets for a specific group of companies
        :param group: group of companies to return
        :param extend_targets:  (False) For each year, skip companies without an active target.
                                (True) Account all companies in all years, keeping target baselines for pre-target years
        :return: total electricity, renewable electricity [index=companies, columns=2015--2019], values in MWh
                 targeted renewable ratio [index=companies, columns=2015--2019], values in %
        """
        years = self.years
        energy = self.energy
        target_ratios = self.target_ratios.loc[group, years].copy()
        t_elec = pd.DataFrame(index=group, columns=years)
        re_elec = pd.DataFrame(index=group, columns=years)

        if extend_targets:
            # Fill with baseline/final emission values
            for company in group:
                if target_ratios.loc[company].count() > 0:
                    base_yr = target_ratios.loc[company].first_valid_index()
                    target_ratios.loc[company, :base_yr] = target_ratios.loc[company, base_yr]
        else:
            target_ratios = target_ratios.fillna(0)

        for company in group:
            for year in years:
                if not pd.isnull(target_ratios.loc[company, year]):
                    company_energy = energy.loc[company]
                    p_t_elec = company_energy["ct purchased electricity " + str(year)]
                    sc_t_elec = company_energy["gt self-cons electricity " + str(year)]
                    t_elec.loc[company, year] = p_t_elec + sc_t_elec

                    p_re_elec = company_energy["cr purchased electricity " + str(year)]
                    sc_re_elec = company_energy["gr self-cons electricity " + str(year)]
                    re_elec.loc[company, year] = p_re_elec + sc_re_elec

        return t_elec, re_elec, target_ratios


class PlotterRE100(PlotterICI):
    def __init__(self):
        super().__init__()
        self.data = RE100()
        self.name = "RE100"

    def plot_all(self, save=False):
        self.plot_bar_joining_year(save)
        self.plot_bar_joining_year_all(save)
        self.plot_pie_overlap_sbti_all(save)
        self.plot_line_electricity_all(save)

    def plot_bar_target_year(self, save=False):
        target_yr = self.data.ici['final year'].value_counts()
        target_yr = target_yr.sort_index(ascending=True)
        target_yr.index = [int(i) for i in target_yr.index]

        plt.figure()
        target_yr.plot.bar(width=.8, color=graphics.COLORMAP['RE100'])
        graphics.plot_config(y_label="N. companies", x_label="Year")
        if save:
            graphics.save_figure("bar_RE100_target_year")

    def plot_bar_joining_year(self, save=False):
        """
        Cumulative RE100 membership in the G500
        :param save:
        :return:
        """
        joining_yr = self.data.ici['joining year'].value_counts()
        joining_yr = joining_yr.sort_index(ascending=True)
        joining_yr.index = [int(i) for i in joining_yr.index]

        count = 0
        for year in joining_yr.index:
            count += joining_yr[year]
            joining_yr[year] = count

        color = graphics.get_colors(['RE100'])
        graphics.bar([joining_yr.values], joining_yr.index, 'RE100 companies', color, num_show=True)
        graphics.plot_config(y_label="Companies")

        if save:
            graphics.save_figure("bar_RE100_cumulative_membership")

    def plot_line_target_ratio(self, company):
        ratio = self.data.target_ratios.loc[company, :]
        years = self.data.target_ratios.columns
        plt.plot(years, ratio)

    def plot_line_target_ratio_all(self, save=False):

        plt.figure()
        graphics.plot_config(y_ax_percent=True)

        target_ratios = self.data.target_ratios
        companies = target_ratios.index
        for col in target_ratios.columns:
            for company in companies:
                if target_ratios.loc[company, col]:
                    value = target_ratios.loc[company, col]
                    plt.plot(col, value, '.', color='red')

        graphics.plot_config(title='RE100: targeted renewable electricity in\n'+str(len(companies)) +
                             ' companies that joined up to 2019', y_label="% RE", x_label='Year')
        if save:
            graphics.save_figure("line_RE100_target_ratios")

    def plot_bar_joining_year_all(self, save=False):
        """
        Cumulative membership in all of RE100 until 2020
        :param save:
        :return:
        """
        year = list(range(2014, 2021))
        members = [13, 38, 31, 34, 39, 64, 42]

        tmp = 0
        cumulative = []
        for i in members:
            tmp += i
            cumulative.append(tmp)
        plt.figure()
        plt.bar(year, cumulative, color=self.colors['RE100'])
        graphics.plot_config(y_label='N. companies', legend=False)
        if save:
            graphics.save_figure("RE100_joining_all")

    def plot_pie_overlap_sbti_all(self, save=False):
        only_re100 = 117
        at_1_5 = 62
        around_2 = 44
        committed = 38

        labels = ["Only RE100 (" + str(only_re100) + ')', "1°5 C (" + str(at_1_5) + ')',
                  "2°C/well-below 2°C (" + str(around_2)+')', "Committed ("+str(committed)+')']
        values = [only_re100, at_1_5, around_2, committed]

        colors = [self.colors['RE100'], self.colors['1.5°C'], self.colors['2°C'], self.colors['Committed']]

        plt.figure()
        _, _, autopcts = plt.pie(values, radius=1, autopct='%.1f%%', startangle=270,
                                 pctdistance=0.6, wedgeprops=dict(edgecolor='white'),
                                 colors=colors)

        plt.legend(labels=labels)

        plt.tight_layout()

        plt.setp(autopcts, **{'weight': 'bold', 'fontsize': 12.5})

        plt.axis('equal')
        plt.show()
        if save:
            graphics.save_figure('pie_re100_sbti_overlap_all')

    @staticmethod
    def plot_line_electricity_all(save=False):
        total = [109, 159, 188, 229, 278]
        percent = [.22, .32, .38, .38, .42]
        renewable = [i*j for i, j in zip(total, percent)]
        percent = [i*100 for i in percent]

        year = list(range(2015, 2020))

        fig, ax1 = plt.subplots()

        ax1.set_ylabel('TWh', fontweight='bold')
        l1 = ax1.plot(year, total, color='#D55E00', label='Total electricity', lw=2)
        l2 = ax1.plot(year, renewable, color='#009E73', label="Renewable electricity", lw=2)
        plt.fill_between(year, renewable, color='#009E73', alpha=.5)

        ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis

        color = 'blue'
        ax2.set_ylabel('RE %', color=color, fontweight='bold')  # we already handled the x-label with ax1
        l3 = ax2.plot(year, percent, color=color, linestyle='--', label='Share of renewables')
        ax2.tick_params(axis='y', labelcolor=color)

        lns = l1+l2+l3
        labs = [i.get_label() for i in lns]
        ax1.legend(lns, labs)

        ax2.yaxis.set_major_formatter(graphics.mticker.PercentFormatter())
        ax2.grid(False)
        plt.ylim([0, 100])

        fig.tight_layout()  # otherwise the right y-label is slightly clipped
        plt.show()

        graphics.plot_config(legend=False, int_xticks=True)

        if save:
            graphics.save_figure("RE100_electricity_all_members")

    def plot_re100_mean_ratios(self, save=False):
        """
        Shows the mean ratio of targets and achieved mean ratio over time.
        :return:
        """
        plt.figure()

        avg_target = self.data.target_ratios.mean()
        avg_target.name = 'mean target ratio (' + str(len(self.data.index_baseline_pre_2020)) + ')'
        avg_target.plot.line('o')

        # get only pre 2020 companies and remove non-members year-by-year
        pre_2020_ratios = self.data.re_electricity_ratios.loc[self.data.index_baseline_pre_2020, :]
        for year in self.data.target_ratios.columns:
            for company in self.data.target_ratios.index:
                if np.isnan(self.data.target_ratios.loc[company, year]):
                    pre_2020_ratios.loc[company, year] = np.nan

        avg_re = pre_2020_ratios.mean()
        avg_re.name = 'mean renewable electricity ratio (' + str(len(pre_2020_ratios.index))+')'
        avg_re.plot.line('v')

        graphics.plot_config(y_label="RE %", y_ax_percent=True, legend=True)
        if save:
            graphics.save_figure("RE100_mean_ratios")

    def plot_re100_electricity(self, save=False):

        target_ratios = self.data.target_ratios.loc[:, 2015:2019]

        electricity = self.data.total_electricity.loc[target_ratios.index, :]
        electricity_ratios = self.data.re_electricity_ratios.loc[target_ratios.index, :]

        re_achieved = pd.DataFrame()
        re_targeted = pd.DataFrame()
        for year in target_ratios.columns:
            re_achieved[year] = electricity[year]*electricity_ratios[year]
            re_targeted[year] = electricity[year]*target_ratios[year]
            for company in re_targeted.index:
                if np.isnan(re_targeted.loc[company, year]):
                    re_achieved.loc[company, year] = np.nan

        results = pd.DataFrame()
        results['targets'] = pd.DataFrame.sum(re_targeted) / 10**6
        results['achieved'] = pd.DataFrame.sum(re_achieved) / 10**6

        results[['targets', 'achieved']].plot.line()
        graphics.plot_config(title='Targeted and achieved renewable electricity\n use in RE100 companies',
                             x_label='Year', y_label='TWh', int_xticks=True)
        plt.fill_between(results.index, results.achieved, facecolor='blue', alpha=.2)

        if save:
            graphics.save_figure('re100_re_electricity')

    def plot_box_re100_ambition(self, index, central_grouping=None, save=False):
        target_ratios = self.data.target_ratios.loc[index]

        if central_grouping:
            groups, names, n_sets = self.get_central_grouping(index, central_grouping, n_set_df=target_ratios)
        else:
            groups = [index]
            names = [""]
            n_sets = [target_ratios.count()]

        for group, name, n_set in zip(groups, names, n_sets):
            ratios = target_ratios.loc[group]
            ax = ratios.plot.box(showfliers=True)
            labels = ["SSP1-1.5 OECD", "SSP2-Base OECD"]
            label_name = ["1.5°C OECD", "Baseline OECD"]
            for i, scenario in enumerate(["SSP1-19 OECD", "SSP2-Base OECD"]):
                years, mini, maxi = ipcc_scenarios.get_ipcc_re_electricity_benchmark(scenario, start_year=2014)
                x_tick_pos = list(range(1, len(years) + 1))  # This one is necessary because line+box plots act funky
                color = graphics.get_colors(labels[i])[0]
                ax.plot(x_tick_pos, mini, color=color, label=label_name[i])
                ax.plot(x_tick_pos, maxi, color=color)
                plt.fill_between(x_tick_pos, mini, maxi, color=color, alpha=.3)

            plt.locator_params(axis='x', nbins=10)
            x_ticks = ax.get_xticks().astype(int).tolist()
            ax.xaxis.set_major_locator(graphics.mticker.FixedLocator(x_ticks))
            fix_ticks = [i + 2013 for i in x_ticks]
            ax.set_xticklabels(["%d\n$n$=%d" % (2013 + x, n) for x, n in zip(x_ticks, n_set.loc[fix_ticks])])

            graphics.plot_config(y_label="Targeted RE in total electricity", y_ax_percent=True, legend=True,
                                 legend_loc='lower right')
            graphics.legend_add_marker(ax, "Outlier", 'o', 'black')
            if save:
                filename = "RE100_ambition_box_"
                folder = "re100_ambition"
                if central_grouping:
                    graphics.save_figure(filename + name, folder=folder)
                else:
                    graphics.save_figure(filename + "all", folder=folder)

    def plot_line_re100_ambition(self, index, central_grouping=None, save=False):
        target_ratios = self.data.target_ratios.loc[index]

        if central_grouping:
            groups, names, n_sets = self.get_central_grouping(index, central_grouping, n_set_df=target_ratios)
        else:
            groups = [index]
            names = [""]
            n_sets = [target_ratios.count()]

        for group, name, n_set in zip(groups, names, n_sets):
            re_twh = self.data.get_baseline_targeted_re_electricity_extended()
            re_twh = pd.DataFrame.sum(re_twh.loc[group])
            twh = self.data.get_baseline_total_electricity_extended()
            twh = pd.DataFrame.sum(twh.loc[group])
            ambition = pd.DataFrame([re_twh, twh]).astype('float') / self.MAGNITUDE
            ambition.index = ["Renewable", "Total"]
            years = ambition.columns

            _, ax = plt.subplots()
            ax = ambition.T.plot.line(ax=ax, color=graphics.get_colors(ambition.index), linewidth=2)
            plt.fill_between(years, ambition.iloc[0], facecolor=graphics.get_colors("Renewable"), alpha=0.5)
            ax.set_xticks(range(2014, 2051, 4))
            x_ticks = ax.get_xticks().astype(int).tolist()
            graphics.show_sample_size_xticks(ax, x_ticks, n_set.loc[x_ticks], fix=True)
            graphics.plot_config(y_label="Electricity ($TWh$)", title=name, legend=True, legend_loc='lower right')

            if save:
                filename = "RE100_ambition_line_"
                folder = "re100_ambition"
                if central_grouping:
                    graphics.save_figure(filename + name, folder=folder)
                else:
                    graphics.save_figure(filename + "all", folder=folder)

    def plot_line_re100_substantive(self, index, central_grouping=None, extend=False, y_max=None, legend=True,
                                    save=False):
        years = self.data.years
        target_ratios = self.data.target_ratios.loc[index, years]

        if extend:
            t_sub_label = " (extended)"
            r_sub_label = ""
        else:
            t_sub_label = ""
            r_sub_label = " (active)"

        if central_grouping:
            groups, names, n_sets = self.get_central_grouping(index, central_grouping, n_set_df=target_ratios)
        else:
            groups = [index]
            names = [""]
            n_sets = [target_ratios.count()]

        for i, group in enumerate(groups):
            total, renewable, target_ratios = self.data.get_re100_targeted_results(group, extend_targets=extend)
            targeted = pd.DataFrame.sum(total*target_ratios).astype(float) / self.MAGNITUDE
            renewable = pd.DataFrame.sum(renewable).astype(float) / self.MAGNITUDE
            total = pd.DataFrame.sum(total).astype(float) / self.MAGNITUDE

            _, ax = plt.subplots()
            targeted.plot(ax=ax, label="Targets"+t_sub_label, color=graphics.get_colors("Targets"), lw=2, style='o-',
                          legend=None)
            renewable.plot(ax=ax, label="Achieved RE"+r_sub_label, color=graphics.get_colors("Renewable"), lw=2,
                           legend=None)
            total.plot(ax=ax, label="Total", color=graphics.get_colors("Total"), linewidth=2)
            plt.fill_between(years, renewable, color=graphics.get_colors('Renewable'), alpha=0.5)
            if y_max:
                ax.set_ylim(top=y_max)
            graphics.show_sample_size_xticks(ax, years, n_sets[i], fix=True)
            graphics.plot_config(y_label="Electricity ($TWh$)", int_xticks=True, legend=legend)
            if save:
                filename = "RE100_substantive_"
                if extend:
                    filename += "ex_"
                if central_grouping:
                    graphics.save_figure(filename + names[i], folder="re100_substantive")
                else:
                    graphics.save_figure(filename + "all", folder="re100_substantive")

    def plot_bar_re100_substantive(self, index, central_grouping=None, legend=True):
        years = self.data.years
        target_ratios = self.data.target_ratios.loc[index, years]

        if central_grouping:
            groups, names, n_sets = self.get_central_grouping(index, central_grouping, n_set_df=target_ratios)
        else:
            groups = [index]
            names = [""]
            n_sets = [target_ratios.count()]

        total, renewable, target_ratios = self.data.get_re100_targeted_results(index, extend_targets=False)
        for group, name, n_set in zip(groups, names, n_sets):
            targeted = total.loc[group]*target_ratios.loc[group]
            re_result_group = renewable.loc[group].mask(targeted.loc[group].isna())

            tracker = pd.DataFrame(index=years)
            tracker["On target"] = targeted[targeted < re_result_group].count()
            tracker["Not on target"] = targeted.count() - tracker['On target']
            tracker = tracker.replace(0, "")
            ax = tracker.plot.bar(stacked=True, color=["#56B4E9", "#D55E00"], rot=0)
            labels = [tracker["On target"].values, tracker["Not on target"].values]
            for c, label in zip(ax.containers, labels):
                ax.bar_label(c, labels=label, label_type='center', fontweight='bold')
            graphics.show_sample_size_xticks(ax, years, n_set)
            graphics.plot_config(y_label="Companies", legend=legend, legend_reverse=True)

    def plot_pie_re100_context(self, save=False):
        missing = ["M&G", "Seven & I Holdings"]
        ici = self.data.ici.drop(missing)
        joining = ici.value_counts('joining year').sort_index()

        inside = sum(joining[joining.index <= 2019])
        baseline = sum(joining[joining.index == 2020])
        outside = sum(joining[joining.index > 2020])
        exempt = len(missing)
        counts = [inside, baseline, outside, exempt]
        colors = ["All indicators", "Only ambition", "None", "Missing"]
        labels = [c + ' (' + str(i) + ')' for i, c in zip(counts, colors)]
        graphics.pie(counts, labels, color_names=colors)
        if save:
            graphics.save_figure("pie_RE100_context")

    def plot_bar_re100_context(self, save=False):
        counts = pd.DataFrame(index=range(2014, 2022))
        counts['Joining year'] = self.data.ici.value_counts('joining year')
        counts['Baseline year'] = self.data.ici.value_counts('baseline year')
        counts = counts.fillna(0)
        for col in counts.columns:
            tmp = 0
            for index in counts.index:
                tmp += counts.loc[index, col]
                counts.loc[index, col] = tmp
        counts.plot.bar(color=graphics.COLORBLIND, rot=0, width=0.8)
        graphics.plot_config()
        if save:
            graphics.save_figure("bar_RE100_context")

    def plot_line_target_linearization(self, save=False):
        _, ax = plt.subplots()
        colors = graphics.COLORBLIND

        for i, company in enumerate(["Panasonic", "Daiwa House Industry"]):
            self.data.target_ratios.loc[company].plot(ax=ax, label=company, color=colors[i], linewidth=2.5)
        graphics.plot_config(y_label="RE in electricity", y_ax_percent=True, legend=True)
        ax.axvline(2030, color='black', linestyle='--')
        plt.text(2030, 0.1, "Min. interim 60%", rotation=90, ha='right')
        ax.axvline(2040, color='black', linestyle='--')
        plt.text(2040, 0.1, "Min. interim 90%", rotation=90, ha='right')
        if save:
            graphics.save_figure("line_RE100_linearization")

    def plot_bar_indexes(self, central_grouping="energy sector", barh=False):
        base2020 = self.data.index_baseline_pre_2020
        join2019 = self.data.index_analysis

        bar = pd.DataFrame()

        name = "Baseline pre 2020 (" + str(len(base2020)) + ")"
        bar[name] = self.data.central.loc[base2020].value_counts(central_grouping)
        name = "Joined 2014-2019 (" + str(len(join2019)) + ")"
        bar[name] = self.data.central.loc[join2019].value_counts(central_grouping)

        _, ax = plt.subplots()
        if barh:
            bar.plot.barh(ax=ax, rot=0, color=graphics.COLORBLIND)
            ax.yaxis.label.set_visible(False)
            graphics.plot_config(x_label="Companies", legend=True, legend_reverse=True)
        else:
            bar.plot.bar(ax=ax, rot=0, color=graphics.COLORBLIND)
            ax.xaxis.label.set_visible(False)
            graphics.plot_config(y_label="Companies")

    def context(self):
        self.plot_pie_re100_context(True)
        self.plot_bar_re100_context(True)
        self.plot_line_target_linearization(True)

    def other(self):
        folder = "re100_other"
        self.plot_pie_by_central(self.data.index_baseline_pre_2020)
        graphics.save_figure("RE100_baseline_sample", folder=folder)
        self.plot_bar_indexes(barh=True)
        graphics.save_figure("RE100_energy_samples", folder=folder)
        self.plot_bar_indexes(central_grouping='gics sector', barh=True)
        graphics.save_figure("RE100_gics_samples", folder=folder)
        self.plot_line_s12_by_scope(self.data.index_analysis)

    def ambition(self, save=False):
        index = self.data.index_baseline_pre_2020
        self.plot_box_re100_ambition(index, save=save)
        self.plot_line_re100_ambition(index, save=save)
        self.plot_box_re100_ambition(index, central_grouping="energy sector", save=save)
        self.plot_line_re100_ambition(index, central_grouping="energy sector", save=save)
        self.plot_box_re100_ambition(index, central_grouping="gics sector", save=save)
        self.plot_line_re100_ambition(index, central_grouping="gics sector", save=save)

    def substantive(self, save=False):
        index = self.data.index_analysis
        self.plot_line_re100_substantive(index, save=save, y_max=175)
        self.plot_line_re100_substantive(index, extend=True, save=save, y_max=175)
        self.plot_line_re100_substantive(index, central_grouping="energy sector", extend=True, y_max=115, save=save)
        self.plot_line_re100_substantive(index, central_grouping="gics sector", extend=True, save=save)


# tst = PlotterRE100()
# ind = tst.data.index_analysis
# targs = tst.data.target_ratios
# tst.plot_line_re100_ambition(ind, central_grouping='energy sector')
# tst.plot_box_re100_ambition(ind, central_grouping='energy sector')
