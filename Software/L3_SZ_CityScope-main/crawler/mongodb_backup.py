import pymongo

def do_backup(db, source_collection_name, backup_collection_name):
    source_collection = db[source_collection_name]
    backup_collection = db[backup_collection_name]
    data = list(source_collection.find({}))
    print('num of data: ', len(data))
    backup_collection.insert_many(data)
    print('Backup finished to collection "{}"'.format(backup_collection_name))
    
    
def main():
    db_name = 'L3_SZ_CityScope'
    
    # backup the detailed houses in order to remove duplicate
    # source_collection_name = 'house_detailed_second_hand_lianjia'
    # backup_collection_name = '_backup1_' + source_collection_name
    
    # source_collection_name = 'house_summary_second_hand_lianjia'
    # backup_collection_name = '_backup1_' + source_collection_name + '_with_duplicates'
    
    source_collection_name = 'house_detailed_second_hand_lianjia'
    backup_collection_name = '_backup2_' + source_collection_name + '_FT_over'
    
    client = pymongo.MongoClient('localhost', 27017)  
    db = client[db_name]   

    do_backup(db, source_collection_name, backup_collection_name)

if __name__ == '__main__':
    main()