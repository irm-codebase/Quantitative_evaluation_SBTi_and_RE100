from bs4 import BeautifulSoup
from bs4.element import Tag
from bs4.element import NavigableString
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from datetime import datetime
import warnings


def sort_cdp_responses(html_paths):
    """
    Reorders a list of html paths, and obtains the version
    :param list html_paths: paths of the html files. Max 5.
    :return:
    """
    if len(html_paths) > 5:
        raise ValueError("Pre-sorting: too many html paths given")

    cdp = {}

    for html_path in html_paths:
        html_path = html_path.replace("file://", '')
        with open(html_path) as file:
            soup = BeautifulSoup(file, "html.parser")

        version = check_version(soup)
        if version in cdp:
            raise ValueError("Pre-sorting: version", version, "already exists")
        else:
            cdp[version] = html_path

    cdp_sorted = {}
    for version in sorted(cdp.keys(), reverse=True):
        cdp_sorted[version] = cdp[version]

    return cdp_sorted


def parse_cdp_response(version, html_path, excel_path):
    """
    Combines all the parsers.
    :param int version: CDP questionnaire version
    :param str html_path: path of html file
    :param str excel_path: path of excel output file
    :return:
    """
    # Clean the filepath if needed
    html_path = html_path.replace("file://", '')
    with open(html_path) as file:
        soup = BeautifulSoup(file, "html.parser")

    n_years = check_reporting_dates(soup, version)

    wb = load_workbook(excel_path)
    ws_emissions = wb['Emissions']
    ws_energy = wb['Energy']
    ws_sourcing = wb['S2 MB sourcing']
    ws_utilities = wb['Energy Utility specific']

    # Emissions
    parse_base_emissions(soup, version, ws_emissions)
    parse_methodology(soup, version, ws_emissions)
    parse_verification(soup, version, ws_emissions)
    parse_scope1_emissions(soup, version, ws_emissions, n_years)
    parse_scope2_emissions(soup, version, ws_emissions, n_years)
    parse_scope_3_emissions(soup, version, ws_emissions)

    # Energy
    utility_flag = parse_utilities(soup, version, ws_utilities)
    # if not utility_flag:
    # Completely avoid taking energy consumption info for utilities
    parse_energy_use(soup, version, ws_energy)
    parse_energy_production(soup, version, ws_energy)
    check_utility_flag(utility_flag, version, ws_energy, ws_emissions)

    # Energy sourcing
    parse_scope2_mb_low_carbon(soup, version, ws_sourcing)

    wb.save(excel_path)


def is_version_old(version):
    """
    For path selection in most functions. Uses the value given by check_version.
    :param int version: CDP questionnaire version
    :return:
    """
    if 2016 <= version <= 2017:
        return True
    elif 2018 <= version <= 2020:
        return False
    else:
        raise ValueError("You gave an invalid version: ", version)


def check_version(soup):
    """
    Returns the version of the CDP questionnaire.
    :param soup: page html in bs4 format
    :return:
    """
    response = soup.find(id='formatted_responses_ndp__container')
    if response is not None:
        title = response.contents[3].contents[0]
        title = title.split(' - ')
        txt = title[-1][-4:]
    else:
        response = soup.find(id='formatted_response__container')
        title = response.contents[1].contents[0]
        title = title.split(' - ')
        txt = title[0][-4:]
    version = int(txt)
    if 2015 < version < 2021:
        return version
    else:
        raise ValueError("Input file is not a valid questionnaire")


def check_reporting_dates(soup, version):
    """
    Checks if the version and the reported date match.
    Returns the number of reported years if all the info matches. If anything does not match, generates an error.
    :param soup: the html file, soup thing
    :param version: version of the questionnaire.
    :return:
    """
    if is_version_old(version):
        # raise ValueError("C0.2 reporting dates: only use for 2018-2020 questionnaires. You gave version", version)
        question = get_question_old(soup, "ORSMENU_0", "CC0.2")
        table = get_table_from_section(question, 'cdp-question-body-table', version)
        [start, end] = table[1][0].split(' - ')
        year = check_year_delta(start, end, "CC0.2 reporting start/end", date_format="%a %d %b %Y")
        if year+1 != version:
            warnings.warn("CC0.2: the reporting start/end does not match the questionnaire version")
        n_years_reported = 1
        return n_years_reported
    else:
        question = get_section_new(soup, 'formatted_responses_matrix_set_grid_11995')
        table = get_table_from_section(question, 'ndp_formatted_response__table', version)
        if table[0][1] == "Start date":
            year = check_year_delta(table[1][1], table[1][2], "C0.2 reporting start/end")
            if year + 1 != version:
                warnings.warn("C0.2: the reporting start/end does not match the questionnaire version.")
            # Check if they are reporting more than one year
            if table[1][3] == "Yes" and table[1][4] != "Please select":
                n_years_reported = int(table[1][4][0]) + 1
            else:
                n_years_reported = 1
            if 0 < n_years_reported <= 4:
                return n_years_reported
            else:
                raise ValueError("C0.2 invalid number of reported years found")


def check_year_delta(date1_txt, date2_txt, section_name, min_delta=361, max_delta=369, date_format="%B %d %Y"):
    """
    Compares two dates and sees if a year passed between them.
    If that is true, returns the year where the most portion of that time passed
    :param str date1_txt: Date string, oldest date
    :param str date2_txt: Date string, newest date
    :param str section_name: Name of the section you are testing, used for warning messages
    :param int min_delta: minimum difference allowed between the dates. Default 363.
    :param int max_delta: maximum difference allowed between the dates. Default 367.
    :param str date_format: string formatting for the datetime library. Default Month DD YYYY. Eg. January 1 2017.
    :return: 
    """
    year_start = datetime.strptime(date1_txt, date_format)
    year_end = datetime.strptime(date2_txt, date_format)
    delta = year_end - year_start
    if delta.days < min_delta:
        warnings.warn("WARNING: submitted dates for:" + section_name + "are less than a full year apart")
        return None
    if max_delta < delta.days:
        warnings.warn("WARNING: submitted dates for:" + section_name + " are more than a full year apart")
        return None
    if year_start.month < 7:
        year = year_start.year
    else:
        year = year_end.year
    return year


def parse_base_emissions(soup, version, sheet):
    """
    Fetches base emissions and puts them in an excel.
    Only for new questionnaire.
    Section C5.1
    :param soup: html
    :param int version: questionnaire version verifier
    :param Worksheet sheet: Exel sheet to fill in
    :return:
    """

    if is_version_old(version):
        return
    else:
        question_ids = ['formatted_responses_question_2723', 'formatted_responses_question_2727',
                        'formatted_responses_question_2731']
        if sheet["E3"].value or sheet['F3'].value:
            # Already parsed
            return
        for question_id in question_ids:
            scope = get_section_new(soup, question_id)
            info = html_section_2_list(scope)
            if "Scope 1" in info[0]:
                column = 'E'
            elif "Scope 2 (location-based)" in info[0]:
                column = 'F'
            elif "Scope 2 (market-based)" in info[0]:
                column = 'G'
            else:
                raise ValueError("C5.1 base emissions: could not find valid Scope type")

            try:
                tco2e = float(info[6])
            except (ValueError, IndexError) as e:
                warnings.warn("C5.1 base emissions: "+info[0]+" base emissions not given. Version "+str(version))
                continue
            sheet[column + '3'] = tco2e
            year = check_year_delta(info[2], info[4], "C5.1 base emissions")
            sheet[column + '4'] = year


def parse_methodology(soup, version, sheet):
    """
    Fetches standard/protocol/methodology used and puts it in the excel.
    Grabs the first found of the following: GHG Protocol, ISO14064-1, The Climate Registry (TCR)
    Otherwise, it fills 'Other' and gives a warning.
    Only for new questionnaire.
    Section C5.2.
    :param soup: html
    :param int version: questionnaire version verifier
    :param Worksheet sheet: Exel sheet to fill in
    :return:
    """
    if is_version_old(version):
        return
    else:
        if sheet['B16'].value:
            # Already parsed
            return
        section = get_section_new(soup, "formatted_responses_question_12033")
        info = html_section_2_list(section)
        for text in info:
            if "The Greenhouse Gas Protocol" in text:
                method = 'GHG Protocol'
                break
            elif "ISO 14064-1" in text:
                method = 'ISO14064-1'
                break
            elif "The Climate Registry" in text:
                method = 'The Climate Registry (TCR)'
                break
        else:
            method = 'Other'
            warnings.warn("C5.2 Methodology: common standard could not be found, setting as 'Other'")
        sheet['B16'] = method


def parse_verification(soup, version, sheet):
    """
    Fetches verification info for each scope.
    Meant to be used for the newest available questionnaire.
    :param soup: html
    :param int version: questionnaire version verifier
    :param Worksheet sheet: Exel sheet to fill in
    :return:
    """
    if is_version_old(version):
        return
    else:
        if sheet['B19'].value or sheet['B20'].value or sheet['B21'].value:
            # Already parsed
            return
        section = get_section_new(soup, 'formatted_responses_matrix_set_grid_11582')
        info = html_section_2_list(section)
        for i, text in enumerate([info[3], info[5], info[7]]):
            if text == "No emissions data provided":
                verification = "No data given"
            elif text == "No third-party verification or assurance":
                verification = "No external verification"
            elif text == "Third-party verification or assurance process in place":
                verification = "Third party verification"
            else:
                raise ValueError("C10.1 verification: found invalid text. Got:", text)
            sheet['B' + str(19 + i)] = verification


def parse_scope1_emissions(soup, version, sheet, n_reported_years):
    """
    Fetches info from an html file and puts it in an Excel.
    For new questionnaires, grabs any disclosed year, and checks if the dates/number of disclosures match the
    CDP version.
    For old questionnaires, it just grabs the disclosed info.
    :param soup:
    :param version:
    :param sheet:
    :param n_reported_years:
    :return:
    """
    emissions = []
    if is_version_old(version):
        section = get_question_old(soup, "ORSMENU_3", "CC8.2")
        info = html_section_2_list(section)
        try:
            emissions.append(float(info[2]))
        except ValueError:
            warnings.warn("CC8.2 Scope 1: no emissions could be found in version " + str(version) + ". Probably empty.")
    else:
        dates = []

        section = get_section_new(soup, "formatted_responses_question_18615")
        info = html_section_2_list(section)
        # Fetch info and put it in lists
        for i, txt in enumerate(info):
            if txt == "Gross global Scope 1 emissions (metric tons CO2e)":
                try:
                    emissions.append(float(info[i+1]))
                except ValueError:
                    if info[i+1] == "End-year of reporting period" or info[i+1] == "Start date":
                        warnings.warn("C6.1 Scope 1: emissions value was empty. Version " + str(version))
                        break
                    else:
                        raise ValueError("C6.1 Scope 1: error in tCO2e:", info[i+1], "Version", version)
            if version == 2018:
                if txt == "End-year of reporting period":
                    dates.append(info[i+1])
            else:
                if txt == "Start date":
                    dates.append([info[i+1]])
                elif txt == "End date":
                    dates[-1].append(info[i+1])

        # Do some date validation
        if len(dates) != n_reported_years or len(emissions) != n_reported_years:
            warnings.warn("C6.1 Scope 1: number of reported years does not match section C0.2")
        count = 1
        for date in dates:
            if version == 2018:
                if date != "<Not Applicable>":
                    if int(date) != version-count:
                        warnings.warn("C6.1 scope 1: dates do not match. Expected " + str(version-count) +
                                      " but found " + date + " instead.")
            else:
                if date[0] != "<Not Applicable>" and date[1] != "<Not Applicable>":
                    tmp_year = check_year_delta(date[0], date[1], "C6.1 Scope 1")
                    if tmp_year != version-count:
                        warnings.warn("C6.1 scope 1: dates do not match. Expected " + str(version - count) +
                                      " but found " + str(tmp_year) + " instead.")
            count += 1

    # Put info in Excel
    if emissions:
        if is_version_old(version) and len(emissions) > 1:
            raise ValueError("C6.1 Scope 1: old questionnaires cannot give emissions for more than one year.")
        col_int = 69+(version-2016)  # simple way of finding the column
        row = '19'
        for i, value in enumerate(emissions):
            col = chr(col_int-i)
            sheet[col+row] = value
    else:
        warnings.warn("C6.1 Scope 1: parsed emissions are empty. Version " + str(version))


def parse_scope2_emissions(soup, version, sheet, n_reported_years):
    """
    Fetches info from an html file and puts it in an Excel.
    For new questionnaires, grabs any disclosed year, and checks if the dates/number of disclosures match the
    CDP version.
    For old questionnaires, it just grabs the disclosed info.
    :param soup: html data
    :param version: CDP questionnaire version given by check_version
    :param sheet: excel sheet to input info
    :param n_reported_years: used for date validation in new questionnaires
    :return:
    """
    emissions_lb = []
    emissions_mb = []
    if is_version_old(version):
        # Fetch the values from the html
        section = get_question_old(soup, "ORSMENU_3", "CC8.3a")
        table = get_table_from_section(section, 'cdp-question-body-table', version)
        try:
            emissions_lb.append(float(table[1][0]))
        except ValueError:
            warnings.warn("CC8.3a Scope 2: no LB emissions could be found in version " + str(version))
            emissions_lb.append(None)
        try:
            emissions_mb.append(float(table[1][1]))
        except ValueError:
            warnings.warn("CC8.3a Scope 2: no MB emissions could be found in version " + str(version))
            emissions_mb.append(None)
    else:
        dates = []
        question = get_section_new(soup, 'formatted_responses_question_2816')
        info = html_section_2_list(question)
        for i, txt in enumerate(info):
            # find Scope 2 values
            if txt == "Scope 2, location-based":
                try:
                    emissions_lb.append(float(info[i+1]))
                except ValueError:
                    warnings.warn("C6.3 LB info missing in response version" + str(version))
                    emissions_lb.append(None)
            elif txt == "Scope 2, market-based (if applicable)":
                try:
                    emissions_mb.append(float(info[i+1]))
                except ValueError:
                    warnings.warn("C6.3 MB info missing from response version " + str(version))
                    emissions_mb.append(None)
            # find date information
            elif version == 2018 and txt == "End-year of reporting period":
                dates.append(info[i+1])
            elif txt == "Start date":
                dates.append([info[i+1]])
            elif txt == "End date":
                dates[-1].append(info[i+1])

        # Date validation
        if len(dates) != n_reported_years or (len(emissions_lb) != n_reported_years != len(emissions_mb)):
            warnings.warn("C6.3 Scope 2: reported years do not match section C0.2. Version " + str(version))
        count = 1
        for date in dates:
            if version == 2018:
                if date != "<Not Applicable>" and "Comment" not in date:
                    if int(date) != version-count:
                        warnings.warn("C6.3 scope 2: dates do not match. Expected " + str(version-count) +
                                      " but found " + date + " instead. Version " + str(version))
            else:
                if date[0] != "<Not Applicable>" and date[1] != "<Not Applicable>":
                    try:
                        tmp_year = check_year_delta(date[0], date[1], "C6.1 Scope 1")
                        if tmp_year != version-count:
                            warnings.warn("C6.3 scope 2: dates do not match. Expected " + str(version-count) +
                                          " but found " + str(tmp_year) + " instead. Version " + str(version))
                    except ValueError:
                        warnings.warn("C6.3 scope 2: Invalid date given. Version " + str(version) + ". Year " +
                                      str(version-count))
            count += 1

    if len(emissions_lb) != len(emissions_mb):
        raise ValueError("Scope 2: LB and MB length mismatch. Version", version)

    if emissions_lb and emissions_mb:
        if is_version_old(version) and (len(emissions_lb) > 1 or len(emissions_mb) > 1):
            raise ValueError("C6.3 Scope 2: old questionnaires cannot give emissions for more than one year.")

        col_int = 69+(version-2016)  # simple way of finding the column
        for i, value in enumerate(emissions_lb):
            col = chr(col_int - i)
            if value is not None:
                sheet[col+'20'] = value
            if emissions_mb[i] is not None:
                sheet[col + '21'] = emissions_mb[i]
    else:
        warnings.warn("C6.3 Scope 2: parsed emissions are empty. Version " + str(version))


def parse_scope_3_emissions(soup, version, sheet):
    """
    Fetches Scope 3 info from html and puts it in the Excel.
    :param soup: html object
    :param version: CDP questionnaire version
    :param sheet: Excel sheet where the info will be put
    :return:
    """
    cat_dict = {'Purchased goods and services': 'C1', 'Capital goods': 'C2',
                'Fuel-and-energy-related activities (not included in Scope 1 or 2)': 'C3',
                'Upstream transportation and distribution': 'C4', 'Waste generated in operations': 'C5',
                'Business travel': 'C6', 'Employee commuting': 'C7', 'Upstream leased assets': 'C8',
                'Downstream transportation and distribution': 'C9', 'Processing of sold products': 'C10',
                'Use of sold products': 'C11', 'End of life treatment of sold products': 'C12',
                'Downstream leased assets': 'C13', 'Franchises': 'C14', 'Investments': 'C15',
                'Category 15 (Investments)': 'C15', 'Other (upstream)': 'Other (upstream)',
                'Other (downstream)': 'Other (downstream)'}

    # this uses short category names to make debugging easier
    val_dict = dict.fromkeys(cat_dict.values())
    if is_version_old(version):
        question = get_question_old(soup, 'ORSMENU_3', 'CC14.1')
        table = get_table_from_section(question, 'cdp-question-body-table', version)
        for i, row in enumerate(table[1:]):
            if row[0] in cat_dict:
                cat = cat_dict[row[0]]
                if row[1] == "Relevant, calculated" or row[1] == "Not relevant, calculated":
                    try:
                        val_dict[cat] = float(row[2])
                    except ValueError:
                        warnings.warn("CC14.1 Scope 3: empty value in category "+cat+" marked as calculated. Version" +
                                      str(version))
                        val_dict[cat] = "Omitted"
                else:
                    val_dict[cat] = "Omitted"
    else:
        question = get_section_new(soup, 'formatted_responses_question_2325')
        info = html_section_2_list(question)
        # Financial companies have Investments in a separate section for version 2020
        if version == 2020:
            question = get_section_new(soup, 'formatted_responses_question_87916', optional=True)
            if question:
                info += html_section_2_list(question)
        # Fill Scope 3 dictionary
        cat = None
        calculated_flag = False
        for i, txt in enumerate(info):
            # First find what category it is:
            if txt in cat_dict:
                cat = cat_dict[txt]
            elif txt == "Evaluation status":
                status = info[i+1]
                if status == "Relevant, calculated" or status == "Not relevant, calculated":
                    calculated_flag = True
            elif txt == "Metric tonnes CO2e" or txt == "Scope 3 portfolio emissions (metric tons CO2e)":
                if calculated_flag:
                    try:
                        val_dict[cat] = float(info[i+1])
                    except ValueError:
                        val_dict[cat] = "Omitted"
                        warnings.warn("C6.5 Scope 3: empty value in category " + cat + " marked as calculated. " +
                                      "Version " + str(version))
                    calculated_flag = False
                else:
                    val_dict[cat] = "Omitted"

    # Info to Excel
    col = chr(69 + (version - 2016))
    row_int = 24
    for i, cat in enumerate(val_dict):
        if val_dict[cat] is None:
            warnings.warn("Scope 3: could not find " + cat + " in version " + str(version))
        elif val_dict[cat] != "Omitted":
            sheet[col+str(row_int+i)] = val_dict[cat]


def parse_energy_use(soup, version, sheet, validate=False):
    """
    Fetches energy use form the CDP questionnaire.
    :param soup:
    :param version:
    :param sheet:
    :param validate:
    :return:
    """
    row_table_2_xl = {'Consumption of fuel (excluding feedstock)': 12,
                      'Consumption of purchased or acquired electricity': 15,
                      'Consumption of purchased or acquired heat': None,
                      'Consumption of purchased or acquired steam': None,
                      'Consumption of purchased or acquired cooling': 18,
                      'Consumption of self-generated non-fuel renewable energy': 21,
                      'Total energy consumption': 22}
    year = chr(69 + (version - 2016))

    if is_version_old(version):
        # Old questionnaires are quite incomplete. The only information that can be easily gathered is:
        # Total purchased HSC, Total fuel consumed, Total purchased electricity consumed

        # Total HSC first
        question = get_question_old(soup, 'ORSMENU_3', 'CC11.2')
        table = get_table_from_section(question, 'cdp-question-body-table', version)
        hsc = 0
        n_empty = 0
        for row in table[1:]:
            if row[1] == '':
                n_empty += 1
            else:
                hsc += float(row[1])
        else:
            if n_empty < 3:
                sheet[year+'20'] = hsc
            else:
                warnings.warn("CC11.2 Energy consumption: Total purchased HSC was empty. Version " + str(version))
        # Total Fuel consumed
        question = get_question_old(soup, 'ORSMENU_3', 'CC11.3')
        info = html_section_2_list(question)
        try:
            fuel = float(info[2])
            sheet[year+'14'] = fuel
        except ValueError:
            warnings.warn("CC11.3 Energy consumption: Total fuel consumption was empty. Version " + str(version))
        # Total purchased electricity
        # Verification for this section is done in parse_energy_production
        question = get_question_old(soup, 'ORSMENU_3', 'CC11.5')
        table = get_table_from_section(question, 'cdp-question-body-table', version)
        try:
            purchased_electricity = float(table[1][1])
            sheet[year+'17'] = purchased_electricity
        except ValueError:
            warnings.warn("CC11.5 Energy consumption: Total purchased electricity was empty. Version " + str(version))
    else:
        question = get_section_new(soup, 'formatted_responses_matrix_set_grid_10823')
        table = get_table_from_section(question, 'ndp_formatted_response__table', version)

        # Order is MWh renewable, MWh non-renewable, Total
        hsc = [0, 0, 0]
        total = [0, 0, 0]
        for row in table[1:]:
            consumption = []
            # Grab values
            for value in row[2:]:
                if value == '<Not Applicable>' or value == "N/A" or value == '':
                    consumption.append(0)
                else:
                    consumption.append(float(value))
            else:
                if len(consumption) != 3:
                    raise ValueError("C8.2a Energy Consumption: unexpected consumption length. Version", version)

            # See what row they are and set the row in excel
            xl_row = row_table_2_xl[row[0]]

            # Handle special cases
            if row[0] == "Consumption of purchased or acquired heat" or row[0] == "Consumption of purchased or " \
                                                                                  "acquired steam":
                hsc = [sum(x) for x in zip(hsc, consumption)]
            elif row[0] == "Consumption of purchased or acquired cooling":
                consumption = [sum(x) for x in zip(hsc, consumption)]

            if xl_row is not None:
                # Set all the info in Excel
                if row[0] == "Consumption of fuel (excluding feedstock)":
                    if sheet['J12'].value is None:
                        if 'LHV (lower heating value)' == row[1]:
                            sheet['J12'] = 'LHV'
                        elif 'HHV (higher heating value)' == row[1]:
                            sheet['J12'] = 'HHV'
                        elif 'Unable to confirm heating value' == row[1]:
                            sheet['J12'] = 'Unknown'
                        else:
                            warnings.warn("C8.2a Energy Consumption: Undefined heating value. Version " + str(version))
                    biofuel_sum = check_biofuel_new(soup, version)
                    if biofuel_sum:
                        if check_biofuel_new(soup, version) > consumption[0]:
                            warnings.warn("C8.2a: renewable fuel value smaller than biofuels in section C8.2c in " +
                                          "version " + str(version) + ". Fuel: " + str(biofuel_sum))

                if row[0] == 'Consumption of self-generated non-fuel renewable energy':
                    sheet[year + str(xl_row)] = consumption[-1]
                else:
                    for i, value in enumerate(consumption):
                        sheet[year+str(xl_row+i)] = value

                # Run validation tests
                if consumption[2] != sum(consumption[:-1]) and validate:
                    warnings.warn("C8.2a Energy consumption: Mismatch in Row [" + row[0] + "]. Calculated sum is "
                                  + str(sum(consumption[:-1])) + " but total in html is " + str(consumption[-1]) +
                                  ". Version " + str(version))
                if row[0] == 'Total energy consumption' and validate:
                    for i, (t_sum, t_html) in enumerate(zip(total, consumption)):
                        col_name = table[0][2+i]
                        if t_sum != t_html:
                            warnings.warn("C8.2a Energy consumption. Mismatch in Column [" + col_name + "]." +
                                          " Calculated Sum is " + str(t_sum) + " but total in html is " + str(t_html) +
                                          ". Version " + str(version))
                else:
                    total = [sum(x) for x in zip(total, consumption)]


def parse_energy_production(soup, version, sheet, validate=False):
    """
    Parses energy production.
    :param soup: html page object
    :param int version: CDP questionnaire version, for validation
    :param sheet: excel sheet where the info will be pasted
    :param bool validate: if True, run some validation tests
    :return:
    """
    year = chr(69 + (version - 2016))
    if is_version_old(version):
        # Total produced electricity
        electricity = {'total': 0, 'purchased': 0, 'produced': 0, 're produced': 0, 're produced consumed': 0}

        question = get_question_old(soup, 'ORSMENU_3', 'CC11.5')
        table = get_table_from_section(question, 'cdp-question-body-table', version)
        # Grab values
        for i, col in enumerate(electricity):
            if table[1][i] == '':
                value = 0
            else:
                value = float(table[1][i])
            electricity[col] = value
        # Validate values
        if electricity['produced'] < electricity['re produced']:
            warnings.warn("CC11.5 Energy Production: total electricity production is smaller than RE production. " +
                          "Version " + str(version))
        if electricity['re produced'] < electricity['re produced consumed']:
            warnings.warn("CC11.5 Energy Production: RE produced is smaller than RE produced and consumed. Version " +
                          str(version))
        if electricity['total'] < electricity['re produced consumed']:
            warnings.warn("CC11.5 Energy Production: Total consumption is smaller than RE produced and consumed. " +
                          "Version " + str(version))
        if electricity['total'] < electricity['purchased']:
            warnings.warn("CC11.5 Energy Production: Total consumption is smaller than purchased electricity. " +
                          "Version " + str(version))
        # Put values in Excel
        sheet[year+'28'] = electricity['produced']
        sheet[year+'30'] = electricity['re produced']
        sheet[year+'31'] = electricity['re produced consumed']
    else:
        section = get_section_new(soup, 'formatted_responses_matrix_set_grid_11555', optional=True)
        if section:
            table = get_table_from_section(section, 'ndp_formatted_response__table', version)
            electricity = [0, 0, 0, 0]
            hsc = [0, 0, 0, 0]
            # Fetch values from html
            for row in table[1:]:
                if row[0] == "Electricity":
                    electricity = [0 if r == '' else float(r) for r in row[1:]]
                elif row[0] == "Heat" or row[0] == "Steam" or row[0] == "Cooling":
                    hsc = [h if r == '' else float(r)+h for r, h in zip(row[1:], hsc)]
                else:
                    raise ValueError("C8.2d/e Energy Production: Unexpected energy type found. Version", version)

            # Set values in Excel
            for i, (e, h) in enumerate(zip(electricity, hsc)):
                sheet[year + str(28 + i)] = e
                sheet[year + str(34 + i)] = h

            # Validate values
            if validate:
                if electricity[0] < electricity[1] or electricity[0] < electricity[2] or \
                        electricity[2] < electricity[3]:
                    warnings.warn("C8.2d/e Energy Production: electricity mismatch detected. Version"+str(version))
                if hsc[0] < hsc[1] or hsc[0] < hsc[2] or hsc[2] < hsc[3]:
                    warnings.warn("C8.2d/e Energy Production: HSC mismatch detected. Version"+str(version))

        else:
            print("C8.2d/e Energy Production: section not in questionnaire. Version", version)


def check_biofuel_new(soup, version):
    """
    Reviews the energy fuel section for specific biofuel names, and adds disclosed amounts. Necessary check since
    companies sometimes filled information in the renewable fuels wrong.
    For simplicity, and since accounting these fuels individually is more error prone and some firms did not even bother
    to fill this section, only cases where fuels in this section where larger produce a warning message.

    :param soup: html object
    :param version: CDP questionnaire version
    :return:
    """
    if not is_version_old(version):
        biomass_names = ['Agricultural Waste', 'Animal Fat', 'Animal/Bone Meal', 'Bagasse', 'Bamboo', 'Biodiesel',
                         'Biodiesel Tallow', 'Biodiesel Waste Cooking Oil', 'Bioethanol', 'Biogas', 'Biogasoline',
                         'Biomass Municipal Waste', 'Biomethane', 'Charcoal', 'Grass', 'Hardwood', 'Landfill Gas',
                         'Liquid Biofuel', 'Primary Solid Biomass', 'Softwood', 'Solid Biomass Waste', 'Vegetable Oil',
                         'Waste Paper and Card', 'Wood', 'Wood Chips', 'Wood Logs', 'Wood Pellets', 'Wood Waste',
                         'Turpentine']
        section = get_section_new(soup, 'formatted_responses_question_10853', optional=True)
        if section:
            info = html_section_2_list(section)
            bio_flag = False
            total = 0
            for i, txt in enumerate(info):
                if txt == "Fuels (excluding feedstocks)":
                    if info[i+1] in biomass_names:
                        bio_flag = True
                    else:
                        bio_flag = False
                if bio_flag and txt == "Total fuel MWh consumed by the organization":
                    try:
                        total += float(info[i+1])
                    except ValueError:
                        pass
            return total
        else:
            return None


def parse_utilities(soup, version, sheet, validate=False):
    """
    Obtains information from the Utility-specific section of the questionnaire, runs some validation tests, and returns
    a bool if the questionnaire is from a Utility.
    :param soup:
    :param version:
    :param sheet:
    :param validate: if True, run some tests and give warnings.
    :return: False if not utility, True if utility
    """
    if is_version_old(version):
        # Utility specific questions are not present in old questionnaires.
        return False
    else:
        section = get_section_new(soup, 'formatted_responses_question_8602', optional=True)
        # Only a few companies have this section. Check if it exists in the current questionnaire.
        if section:
            year = chr(66 + (version - 2016))
            technologies = {'Coal – hard': 3, 'Lignite': 4, 'Oil': 5, 'Gas': 6, 'Biomass': 7, 'Waste (non-biomass)': 8,
                            'Nuclear': 9, 'Fossil-fuel plants fitted with CCS': 15, 'Geothermal': 10, 'Hydropower': 11,
                            'Hydroelectric': 11, 'Wind': 12, 'Solar': 13, 'Marine': 14, 'Other renewable': 14,
                            'Other non-renewable': 15}
            tech_values = {"capacity": 0, "gross": 0, "net": 0, "emissions": 0}
            info = html_section_2_list(section)
            info.pop(0)
            technology = None
            row = None
            excel_loc = None
            value_name = None
            for i, txt in enumerate(info):
                if txt in technologies:
                    row = technologies[txt]
                    technology = txt
                    continue
                if row:
                    if txt == "Nameplate capacity (MW)":
                        excel_loc = year+str(row)
                        value_name = 'capacity'
                    elif txt == "Gross electricity generation (GWh)":
                        excel_loc = year+str(row+17)
                        value_name = 'gross'
                    elif txt == "Net electricity generation (GWh)":
                        excel_loc = year+str(row+17*2)
                        value_name = 'net'
                    elif txt == "Absolute scope 1 emissions (metric tons CO2e)":
                        excel_loc = chr(ord(year)+7) + str(row)
                        value_name = 'emissions'
                    elif txt == "Scope 1 emissions intensity (metric tons CO2e per GWh)":
                        row = None

                if excel_loc:
                    try:
                        value = float(info[i+1])
                    except ValueError:
                        value = 0
                    if sheet[excel_loc].value:
                        sheet[excel_loc].value += value
                    else:
                        sheet[excel_loc].value = value
                    excel_loc = None
                    tech_values[value_name] = value

                if value_name == 'emissions':
                    # The information for this technology is complete. Run validation tests.
                    max_generation = tech_values['capacity'] * 365 * 24 / 1000
                    max_capacity = 50000

                    if validate:
                        if tech_values['net'] > tech_values['gross']:
                            warnings.warn("C-EU8.2d/e Utilities: "+technology+" Net > Gross generation. Version " +
                                          str(version))
                        if tech_values['gross'] > max_generation:
                            warnings.warn("C-EU8.2d/e Utilities: "+technology+" impossible Gross generation. Version " +
                                          str(version))
                        if tech_values['net'] > max_generation:
                            warnings.warn("C-EU8.2d/e Utilities: "+technology+" impossible Net generation. Version " +
                                          str(version))
                        if tech_values['capacity'] > max_capacity:
                            warnings.warn("C-EU8.2d/e Utilities: "+technology+" capacity above threshold. Version " +
                                          str(version))
            return True
        else:
            return False


def check_utility_flag(flag, version, energy_sheet, emissions_sheet):
    """
    Sets a specific flag in the Excel sheet and runs some tests to ensure a utility is not labeled as another sector.
    :param flag:
    :param energy_sheet:
    :param emissions_sheet:
    :param version:
    :return:
    """
    if is_version_old(version):
        # it makes no sense to run this for old questionnaires
        return
    industry = emissions_sheet['B6'].value

    # First time setting the value
    if not energy_sheet['B28'].value:
        if flag:
            energy_sheet['B28'] = 'yes'
            if industry != "Utilities":
                warnings.warn("UTILITIES: found utilities section, but industry is not set as 'Utilities'")
        else:
            energy_sheet['B28'] = 'no'
            if industry == "Utilities":
                warnings.warn("UTILITIES: Utilities section not found for a company in that industry")
    elif energy_sheet['B28'].value == 'no' and flag:
        warnings.warn("UTILITIES: Utilities flag was as 'no', but a utilities section was found later.")
    elif energy_sheet['B28'].value == 'yes' and not flag:
        warnings.warn("UTILITIES: Utilities flag is 'yes', but a utilities section is missing in a later questionnaire")


def parse_scope2_mb_low_carbon(soup, version, sheet, messages=True):
    """
    Parses the "low carbon" section of the questionnaire. At this point it should cover every variation,
    But it is very, VERY finicky.
    :param soup:
    :param version:
    :param sheet:
    :param messages:
    :return:
    """
    instruments = {"PPA direct line": ["Power purchase agreement (PPA) with on-site/off-site generator owned by a " +
                                       "third party with no grid transfers (direct line)",
                                       "Off-grid energy consumption from an on-site installation or through a direct" +
                                       " line to an off-site generator owned by another company"],
                   "PPA w/EAC": ["Power purchase agreement (PPA) with a grid-connected generator with energy " +
                                 "attribute certificates",
                                 "Power Purchase Agreement (PPA) with energy attribute certificates",
                                 "Direct procurement contract with a grid-connected generator or Power Purchase " +
                                 "Agreement (PPA), supported by energy attribute certificates",
                                 "Direct procurement contract with a gridconnected generator or Power Purchase " +
                                 "Agreement (PPA), supported by energy attribute certificates"],
                   "PPA no EAC": ["Power purchase agreement (PPA) with a grid-connected generator without energy " +
                                  "attribute certificates",
                                  "Power Purchase Agreement (PPA) without energy attribute certificates",
                                  "Direct procurement contract with a grid-connected generator or Power Purchase " +
                                  "Agreement (PPA), where electricity attribute certificates do not exist or are not " +
                                  "required for a usage claim",
                                  "Direct procurement contract with a gridconnected generator or Power Purchase " +
                                  "Agreement (PPA), where electricity attribute certificates do not exist or are not " +
                                  "required for a usage claim"],
                   "Energy product w/EAC": ["Green electricity products (e.g. green tariffs) from an energy supplier," +
                                            " supported by energy attribute certificates",
                                            "Contract with suppliers or utilities ( e.g. green tariff), supported by " +
                                            "energy attribute certificates",
                                            "Contract with suppliers or utilities, supported by energy attribute " +
                                            "certificates"],
                   "Energy product no EAC": ["Green electricity products (e.g. green tariffs) from an energy supplier" +
                                             ", not supported by energy attribute certificates",
                                             "Contract with suppliers or utilities (e.g. green tariff), not supported" +
                                             " by energy attribute certificates",
                                             "Contract with suppliers or utilities (e.g. green tariff), not backed by" +
                                             " electricity attribute certificates",
                                             "Contract with suppliers or utilities, with a supplier-specific emission" +
                                             " rate, not backed by electricity attribute certificates"],
                   "Unbundled EAC": ["Unbundled energy attribute certificates, Guarantees of Origin",
                                     "Unbundled energy attribute certificates, Renewable Energy Certificates (RECs)",
                                     "Unbundled energy attribute certificates, International REC Standard (I-RECs)",
                                     "Unbundled energy attribute certificates, other - please specify",
                                     "Energy attribute certificates, Guarantees of Origin",
                                     "Energy attribute certificates, Renewable Energy Certificates (RECs)",
                                     "Energy attribute certificates, I-RECs"],
                   "HSC agreement": ["Heat/steam/cooling supply agreement"],
                   "Grid mix": ["Grid mix of renewable electricity"],
                   "Self owned": ["Grid-connected electricity generation owned, operated or hosted by the company, " +
                                  "where electricity attribute certificates do not exist or are not required for a " +
                                  "usage claim",
                                  "Grid-connected generation owned, operated or hosted by the company, with energy " +
                                  "attribute certificates created and retired by company"]}
    technologies = {"Solar": ["Solar", "Solar PV", "Concentrated solar power (CSP)"], "Wind": ["Wind"],
                    "Hydro": ["Hydropower"], "Nuclear": ["Nuclear"],
                    "Biomass": ["Biomass", "Biomass (including biogas)"],
                    "Other tech": ["Marine", "Geothermal", "Tidal"],
                    "Unspecified": ["Low-carbon energy mix"]}

    check_flag = False

    if is_version_old(version):
        xl_loc = {2016: ['A', 3], 2017: ['D', 3]}
        question = get_question_old(soup, 'ORSMENU_3', "CC11.4")
        table = get_table_from_section(question, 'cdp-question-body-table', version)
        [col, row] = xl_loc[version]
        offset = 0
        for i, cdp_row in enumerate(table[1:]):
            # Handle special cases
            if cdp_row[0] == '':
                offset += 1
                continue
            elif "No purchases or generation of low carbon" in cdp_row[0]:
                if len(table[1:]) > 1:
                    warnings.warn("CC11.4 sourcing: 'No purchases' found with other values. Version " + str(version))
                    offset += 1
                    continue
                else:
                    break
            # Get rid of annoying end spaces
            cdp_row = [x[:-1] if x[-1] == " " else x for x in cdp_row[:2]]

            # Find market instrument used
            data = cdp_row[0]
            cell = col + str(row+i-offset)
            for instrument in instruments:
                if data in instruments[instrument]:
                    sheet[cell] = instrument
                    break
            else:
                ambiguous = "Off-grid energy consumption from an onsite installation or through a direct line to an" + \
                            " off-site generator"
                if "Other" in data or data == ambiguous:
                    sheet[cell] = "Check"
                    check_flag = True
                else:
                    raise ValueError("CC11.4 sourcing: invalid sourcing method in version ", version, data)
            # Get MWh bought/sourced
            data = cdp_row[1]
            cell = chr(ord(col) + 2) + str(row+i-offset)
            sheet[cell] = float(data)
    else:
        xl_loc = {2018: ['G', 3], 2019: ['J', 3], 2020: ['M', 3]}
        section = get_section_new(soup, 'formatted_responses_question_11576', optional=True)
        if section is None:
            # This section is optional and may not be present in all questionnaires
            print("C8.2e/f sourcing: no information given. Version " + str(version))
            return
        info = html_section_2_list(section)
        [col, row] = xl_loc[version]
        tech_flag = False
        for i, txt in enumerate(info):
            if i != len(info)-1:
                data = info[i + 1]
                if data[-1] == " ":
                    data = data[:-1]
            else:
                data = None
            # Find market instrument used
            if txt == "Sourcing method" or txt == "Basis for applying a low-carbon emission factor":
                cell = col + str(row)
                for instrument in instruments:
                    if data in instruments[instrument]:
                        sheet[cell] = instrument
                        break
                else:
                    if "Other, please specify" in data or "Other low-carbon technology, please specify" in data \
                            or "other - please specify" in data:
                        sheet[cell] = "Check"
                        check_flag = True
                    elif "None" in data or "No purchases" in data:
                        if len(info) > 13:
                            raise ValueError("C8.2e/f sourcing: No purchases, but info is too long. Version", version)
                        else:
                            break
                    else:
                        raise ValueError("C8.2e/f sourcing: invalid sourcing method in version ", version, data)
            # Get MWh sourced
            elif txt == "MWh consumed accounted for at a zero emission factor" or \
                    txt == "MWh consumed associated with low-carbon electricity, heat, steam or cooling":
                tech_flag = False
                cell = chr(ord(col)+2)+str(row)
                sheet[cell] = float(data)
                row += 1
            # Technology section reached?
            elif txt == "Region of consumption of low-carbon electricity, heat, steam or cooling" or \
                    txt == "Country/region of consumption of low-carbon electricity, heat, steam or cooling":
                tech_flag = False
            elif txt == "Low-carbon technology type":
                tech_flag = True
                cell = chr(ord(col) + 1) + str(row)
                sheet[cell] = ''
                continue
            elif tech_flag:
                data = txt
                if txt[-1] == " ":
                    data = txt[:-1]
                cell = chr(ord(col) + 1) + str(row)
                for technology in technologies:
                    if data in technologies[technology]:
                        sheet[cell].value += technology+';'
                        break
                else:
                    if "Other, please specify" in data or "Other low-carbon technology, please specify" in data or \
                            "Please select" == data:
                        sheet[cell] = "Check"
                        check_flag = True
                    else:
                        raise ValueError("C8.2e/f sourcing: invalid technology in version ", version, data)

    if check_flag and messages:
        if is_version_old(version):
            warnings.warn("CC11.4 Scope 2 MB sourcing: some values need checking. Version " + str(version))
        else:
            warnings.warn("C8.2e/f Scope 2 MB sourcing: some values need checking. Version " + str(version))


def get_section_new(soup, section_id, optional=False):
    """
    Fetches a specific question from new CDP questionnaires, and check for validity.
    :param soup: html object
    :param str section_id: html id of the question.
    :param bool optional: avoids raising an error for sections that might not be present in all questionnaire versions.
    :return:
    """
    question = soup.find(id=section_id)
    if type(question) is Tag:
        return question
    elif optional:
        return None
    else:
        raise ValueError("Could not find section id, got this instead", question)


def get_question_old(soup, module_id, question_code):
    """
    Fetches a specific question section from an old CDP questionnaire.
    :param soup: html object
    :param str module_id: ID of the module you want to search. E.g. "ORSMENU_2"
    :param str question_code: question identifier. E.g. "CC8.1"
    :return:
    """
    if '.' not in question_code:
        raise ValueError('Question code (old) is invalid')
    [page_id, question_id] = question_code.split('.')
    module = soup.find(id=module_id)
    if page_id == "CC0":
        # for CC0 page fetching must be omitted
        question = old_find_question_in_page(module, question_id)
    else:
        page = old_find_page_in_module(module, page_id)
        question = old_find_question_in_page(page, question_id)
    if type(question) is Tag:
        return question
    else:
        raise ValueError("Could not find question (old), got this instead", question)


def old_find_page_in_module(module, page_id):

    module_body = module.find('div', attrs={'class', 'cdp-module-body'})
    for child in module_body.children:
        if type(child.next) is Tag:
            page_head = child.next
            page_title = html_section_2_list(page_head)[0]
            if page_id in page_title:
                return child
    else:
        # Some questionnaires have a glitch that puts the rest of the pages inside the last page of the module
        # last = module_body.contents[-1]
        # for child in last.children:
        #     if type(child.next) is Tag:
        #         page_head = child.next
        #         page_title = html_section_2_list(page_head)[0]
        #         if page_id in page_title:
        #             return child
        module_bodies = module.find_all("div", {"class": "cdp-page"})

        for module_body in module_bodies:
            if type(module_body) is Tag:
                for child in module_body.children:
                    if type(child.next) is Tag:
                        page_head = child.next
                        page_title = html_section_2_list(page_head)[0]
                        if "Page: " + page_id in page_title:
                            if 'cdp-page' in child.attrs['class']:
                                return child
                            else:
                                parent = child.parent
                                if 'cdp-page' in parent.attrs['class']:
                                    return parent
                                else:
                                    break
        else:
            raise ValueError("Could not find page id", page_id, "in old questionnaire.")


def old_find_question_in_page(page, question_id):
    page_body = page.find('div', attrs={'class', 'cdp-page-body'})
    for child in page_body.children:
        if type(child.next) is Tag:
            question_head = child.next
            question_title = html_section_2_list(question_head)[0]
            if question_id in question_title:
                return child
    else:
        raise ValueError("Could not find question id", question_id, "in old questionnaire.")


def get_table_from_section(section, table_class_name, version):
    """
    Wrapper function. Finds the given table name in the section and then runs the html to matrix parser.
    :param section:
    :param table_class_name:
    :param int version: CDP questionnaire version
    :return: matrix
    """
    table = section.find('table', attrs={'class', table_class_name})
    return html_table_2_matrix(table, version)


def html_section_2_list(section, contents=None):
    """
    Gives out a list of the text in a specific section, removing enters.
    Only use this for small portions of the questionnaire.
    Recommended use is for question sections (C4.2, C5.1, etc.)
    :param Tag section: html tag to turn into text
    :param list contents: used for recursion. Never fill this.
    :return:
    """
    if contents is None:
        contents = []
    for i in section.children:
        if type(i) is Tag:
            html_section_2_list(i, contents)
        elif type(i) is NavigableString:
            i = i.replace('\n', '')
            if i != '':
                contents.append(i)
    return contents


def html_table_2_matrix(table, version):
    """
    Returns a matrix of the values in the given html table, including headers.
    :param table: html table section.
    :param int version: CDP questionnaire version
    :return: matrix
    """
    if type(table) is Tag and table.name == 'table':
        data = [[]]
        header_section = table.find('thead')
        body_section = table.find('tbody')
        if is_version_old(version):
            # Go down one level (to 'tr')
            header_section = header_section.next
            body_section = body_section.next
            enter = '\u200b'
        else:
            enter = '\n'
        header_cells = header_section.find_all('th')
        body_cells = body_section.find_all('td')
        if len(body_cells) % len(header_cells) != 0:
            raise ValueError('Table dimensions did not match')
        for i, header in enumerate(header_cells):
            if is_version_old(version):
                cell = header.next.text
            else:
                cell = header.text
            data[0].append(cell.replace(enter, ''))
        for i in range(int(len(body_cells)/len(header_cells))):
            row = []
            for j in range(len(data[0])):
                cell = body_cells.pop(0)
                if is_version_old(version):
                    row.append(cell.next.text.replace(enter, ''))
                else:
                    row.append(cell.text.replace(enter, ''))
            data.append(row)
        return data
    else:
        raise ValueError("Input argument is not a html table.")
