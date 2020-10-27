import enum
import re
from .post_processor import PostProcessor
from ..utils import data_frame_utils

class EspiritoSantoPostProcessor(PostProcessor):
    def __init__(self, agency_name) -> None:
        self.agency_name = agency_name

    def is_aplicable(self):
        return self.agency_name == "espirito_santo"

    def process(self, df):
        self.route = "".join(df.iloc[0]).strip()  # get route row
        df = df[1:]  # remove route
        while (not df.empty) and (not str(df.iat[0,0]).startswith('H')):  # remove rows until hours
            df = df[1:] 
        services = df.iloc[:,0]  # get first column
        hours = df.iloc[0]  # get row with the hours
        df = df.drop(columns=[0])  # remove service column
        df = df[1:]  # remove hour row
        df = df.where(df=='', hours + ':' + df.astype(str))  # append value in hours to dataframe where condition df=='' is not met
        df = data_frame_utils.clean_data(df, split=False)  # remove empty rows and cols without splitting at "\n"s
        services = services[services.astype(bool)][1:].reset_index(drop=True)  # remove empty values
        return self._slice_dataframe(df, services)

    # returns list of tuples with days of service and table
    def _slice_dataframe(self, df, services_df):
        temp_df = df.where(df=='-',df.gt(df.shift(periods=1))).replace({"-":True}) # checks if a row has values smaller than the previous row
        temp_df.iloc[0] = True # ignore first row since there is not previous row
        temp_df = temp_df.all(axis='columns') # boolean reduction

        df_list = []
        prev_index = 0
        services = self.service_to_days(services_df)
        for index, value in temp_df.iteritems():
            print(f"here {index} and {value}")
            if value == False: # service change
                print("1")
                print(df)
                df_list.append((next(services),df[prev_index:index])) # add previous service with sliced dataframe 
                prev_index = index
            if index == temp_df.size-1: # set last service since dataframe is ending
                print("2")
                df_list.append((next(services),df[prev_index:])) # add last service with sliced dataframe
        print(str(df_list)) 
        return df_list

    def route_name(self, df=None):
        return self.route.replace("\uf0e0","-") if self.route else ""

    #Days generator yields the result depending on the dataframe series with the services
    def service_to_days(self, services_df):
        services_dict = {"D.?U.?\\n?":["Monday","Tuesday","Wednesday","Thursday","Friday"],
                    "SÁB.?\\n?":["Saturday"],
                    "DOM.?\\n?":["Sunday"]}

        service_counter = 0
        while True:
            try:
                service_string = services_df.iat[service_counter].replace(" ","").strip()
                for synonym, days in services_dict.items():
                    synonym_regex = re.compile(synonym, re.IGNORECASE)
                    if bool(synonym_regex.search(service_string)):
                        yield days
                service_counter += 1
            except GeneratorExit:
                return
            except:
                yield "None"

    def format_message_records(self, df):
        route_name_regex = re.compile(r"\d+ *(?P<origin>(\w\ ?)+)", flags=re.UNICODE)  # route name regex
        origin = re.search(route_name_regex, self.route_name()).group("origin")  # extract origin group
        stop_time_regex = fr"({data_frame_utils.stop_time_regex}).*"  # allow anything after stop time regex as group 2
        # remove group 2 of stop_time_regex and append origin to flat list
        records = df.replace({stop_time_regex : r'\1'}, regex=True).to_numpy().flatten().tolist()
        records.insert(0,origin)
        
        records = {index:record for index, record in enumerate(records)}  # same format as df.to_dict("records")
        #https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.to_dict.html

        return [records]
