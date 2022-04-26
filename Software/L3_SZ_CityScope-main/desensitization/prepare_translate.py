import os, json, argparse

def get_unique_ch_values(read_path, attr_list=[], save_path=None):
    data = json.load(open(read_path, 'r', encoding='utf-8'))
    features = data['features']
    rst = {}
    for attr in attr_list:
        values = [x['properties'].get(attr, 'null') for x in features]
        unique_values = list(set(values))
        # rst[attr] = unique_values
        rst[attr] = {str(x):'' for x in unique_values}
    if save_path is not None:
        json.dump(rst, open(save_path, 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
        print('unique values dict saved to: ', os.path.abspath(save_path))
    return rst 
    
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-rp', default='', help="""read file path""")
    parser.add_argument('-al', default='', help="""comma seperated list of attributes to be analyzed""")
    parser.add_argument('-sf', default='lookup', help="""save folder name""")
    parser.add_argument('-sn', default='', help="""save file name""")
    
    args = parser.parse_args()
    read_path = args.rp
    if args.al == '':
        attr_list = []
    else:
        attr_list = [x.strip() for x in args.al.split(',')]
    save_folder = args.sf
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    save_file_name = args.sn
    print('read_path = {}\nattr_list = {}\nsave_path = {}'.format(
        read_path, attr_list, os.path.abspath(os.path.join(save_folder, save_file_name))))
    get_unique_ch_values(read_path, attr_list, os.path.join(save_folder, save_file_name))
    
if __name__ == '__main__':
    main()
