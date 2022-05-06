import os


class HomeLocChoiceModel:
    def __init__(self):
        pass

    def predict_home_loc(self, persons):
        for person in persons:
            person.home_district = 'FT'
            person.taz = 1
            person.home = {
                'h3': 11,
                'coords': ()
            }


    def predict_district(self, persons):
        pass
        for person in persons:
            person.home_district = 'FT'

    def predict_taz(self,persons):
        for peron in persons:
            person.taz = 1

    def predict_housing_Unit(self):
        for peron in persons:
            person.home = {
                'h3': 11,
                'coords': ()
            }