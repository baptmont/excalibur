import pandas as pd
import numpy as np
from .post_processor import PostProcessor
from ..utils import data_frame_utils

class EspiritoSantoPostProcessor(PostProcessor):
    def __init__(self, agency_name) -> None:
        self.agency_name = agency_name

    def is_aplicable(self):
        return self.agency_name == "espirito_santo"

    def process(self, df):
        self.route = "".join(df.iloc[0]).strip() #get route row
        df = df[1:] #remove route
        while (not str(df.iat[0,0]).startswith('H')) and (not df.empty): #remove rows until hours
            df = df[1:] 
        services = df.iloc[:,0] #get first column
        hours = df.iloc[0] #get row with the hours
        df = df.drop(columns=[0]) #remove service column
        df = df[1:] # remove hour row
        df = df.where(df=='', hours + ':' + df.astype(str)) #append value in hours to dataframe where condition df=='' is not met
        df = data_frame_utils.clean_data(df) #remove empty rows and cols
        services = services[services.astype(bool)][1:].reset_index(drop=True) #remove empty values
        self._slice_dataframe(df, services)
        print(services)
        print(df.to_string())
        return df

    def _slice_dataframe(self, df, services):
        temp_df = df.where(df=='-',df.gt(df.shift(periods=1))).replace({"-":True}) # checks if a row has values smaller than the previous row
        temp_df.iloc[0] = True # ignore first row since there is not previous row
        temp_df = temp_df.all(axis='columns') # boolean reduction
        print(temp_df)

        df_set = {}
        service_counter = 0
        prev_index = 0
        for index, value in temp_df.iteritems():
            print(f"here {index} and {value}")
            if value == False:
                if prev_index == 0:
                    print("1")
                    df_set[services.iat[service_counter]] = df[:index]
                else:
                    print("2")
                    df_set[services.iat[service_counter]] = df[prev_index:index]
                prev_index = index
                service_counter+=1
            if index == temp_df.size-1:
                print("3")
                df_set[services.iat[service_counter]] = df[prev_index:]
                prev_index = index
                service_counter+=1
        print(list(df_set.values()))
        return df_set
            

    def _slice_dataframe_rec(df, services):
        return df

    def route_name(self, df):
        return self.route
