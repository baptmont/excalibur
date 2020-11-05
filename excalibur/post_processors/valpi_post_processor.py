import re
import pandas as pd
from .post_processor import PostProcessor
from ..utils import data_frame_utils

class ValpiPostProcessor(PostProcessor):
    def __init__(self, agency_name) -> None:
        self.agency_name = agency_name

    def is_aplicable_to_agency(self, agency=None):
        try:
            agency = agency if agency else self.agency_name
            return agency == "valpi"
        except:
            return False
    
    def is_aplicable_to_dataframe(self, df=None):
        return True

    service_regex = [re.compile("dias úteis", re.IGNORECASE),
                    re.compile("sábado", re.IGNORECASE),
                    re.compile("domingo", re.IGNORECASE)]

    ignore_words = ["LINHA", "Observações", "Nº Horário", "X Y"]

    def process(self, df):
        self._create_route_name(df.iloc[0])  # get route row
        df = df.replace({"\\n.*":""}, regex=True)  # remove \n and text folowing the \n
        df = df[1:]  # remove route row
        lines = self._create_lines(df)
        
        ignores_dict = {word:'' for word in self.ignore_words + data_frame_utils.ignore_expressions}
        df = data_frame_utils.clean_data(df, ignores_dict=ignores_dict, split=False)  # remove empty rows and cols without splitting at "\n"s
        has_words = df.applymap(lambda x : bool(re.search("[A-Za-z]+",x))).any(axis='columns')  # check the rows with text
        df = df[has_words]  # boolean indexing to filter rows

        services = df.iloc[0]  # get first row
        services = services[1:].reset_index(drop=True)
        return self._slice_dataframe(df, services, lines)

    def _create_route_name(self, series):
        mask = ~series.str.contains("sentido", case = False)
        self.route = "".join(pd.Series(series.values[mask], series.index[mask])).strip()  # format route row

    def _create_lines(self, df):
        lines = df[df.applymap(lambda x : bool(re.search("LINHA",x))).any(axis='columns')].iloc[0] # extract row that has LINHA
        mask = lines.str.contains("\d+", case = False, regex=True)
        lines = pd.Series(lines.values[mask], lines.index[mask]).reset_index(drop=True) # extract columns with numbers 
        return lines

    def _slice_dataframe(self, df, services_df, lines):
        service_gen = self.service_to_days(services_df)  # create generator
        service = next(service_gen)  # get first service
        if(service=="None"):  # if no services were found return None with the entire df
            return [("None",df)]

        df = df[1:].reset_index(drop=True) # remove first row (service row)
        stops = df.iloc[:,0]  # get stops column
        df = df.drop(df.columns[0], axis="columns")
        df.columns = range(df.shape[1])

        df_list = self._create_df_list(df, services_df)  # create the list of sliced dataframes

        cont=0
        result = []
        unique_lines = lines.unique()
        while service != "None":
            sub_df = df_list[cont]
            for line in unique_lines:
                temp_df = sub_df.loc[:, lines == line]  # get sub set of columns where lines is line
                temp_df.insert(0,"Stops",stops)  # add stops column
                temp_df.line = line 
                result.append((service, temp_df))  # add dataframe
            cont +=1
            service = next(service_gen)  # get next result 
        return result

    def _create_df_list(self, df, services_df):
        temp_df = services_df.str.contains("-", case = False)
        temp_df[0] = True

        df_list = []
        prev_index = 0
        for index, value in temp_df.iteritems():
            if value == False:  # service change
                print("1")
                sub_df = df.iloc[:,prev_index:index]
                df_list.append(sub_df) # add previous service with sliced dataframe 
                prev_index = index
            if index == temp_df.size-1: # set last service since dataframe is ending
                print("2")
                sub_df = df.iloc[:,prev_index:]
                df_list.append(sub_df) # add last service with sliced dataframe
        return df_list


    def route_name(self, df=None):
        try:
            return f'{df.line} - {self.route.replace("|","-") if self.route else ""}'
        except:
            return self.route.replace("|","-") if self.route else ""

    #Days generator yields the result depending on the dataframe series with the services
    def service_to_days(self, services_df):
        services_dict = {self.service_regex[0]:["Monday","Tuesday","Wednesday","Thursday","Friday"],
                        self.service_regex[1]:["Saturday"],
                        self.service_regex[2]:["Sunday"]}

        service_counter = 0
        while True:
            try:
                service_string = services_df.iat[service_counter].strip()
                for synonym_regex, days in services_dict.items():
                    if bool(synonym_regex.search(service_string)):
                        yield days
                service_counter += 1
            except GeneratorExit:
                return
            except:
                yield "None"

    def format_message_records(self, df):
        return df.to_dict("records")
