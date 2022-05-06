import os, json, requests, re, time, datetime, random, pymongo, sys
import pandas as pd
from itertools import chain
from bs4 import BeautifulSoup
import parsel
import numpy as np

ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36'


def get_all_page_urls(url_list, mongo_page_url_col=None, save_txt_path=None):   
    # this task do not need an Internet connection so no risk of network failure
    records = []
    for subject in url_list:
        formatted_url, max_page = subject['formatted_url'], subject['max_page']
        for page in range(1, max_page+1):
            this_url = formatted_url.format(page)
            url_obj = {'url': this_url, 'subject': subject['name'], 'page':page, 'finished':False}
            records.append(url_obj)
    if mongo_page_url_col is not None:
        mongo_page_url_col.insert_many(records)
    if save_txt_path is not None:
        if not os.path.exists(os.path.dirname(save_txt_path)): os.makedirs(os.path.dirname(save_txt_path))
        with open(save_txt_path, 'a', encoding='utf-8') as f:
            for url_obj in records:
                f.write(str(url_obj) + '\n')
    
def get_house_url_and_summary_info(url, mongo_house_summary_col=None, save_txt_path=None, proxies={}):
    try:
        headers = {'User-Agent': ua}
        if not proxies:
            time.sleep(random.uniform(0.5,1.0)) 
            res = requests.get(url, headers=headers)
        else:
            res = requests.get(url, headers=headers, proxies=proxies)
        records = []
        if proxies: assert res.status_code == 200
        if res.status_code == 200:
            sel = parsel.Selector(res.text)
            house_list = sel.css('ul.sellListContent li.LOGVIEWDATA div.info')
            for house_sel in house_list:
                house = {}
                house['url'] = house_sel.css('.title a::attr(href)').get()
                if len(list(mongo_house_summary_col.find({'url': house['url']}))) > 0:
                    print('Warning: Duplicated case detected, url = {}'.format(house['url']))
                    continue
                house['title'] = house_sel.css('.title a::text').get()
                house['summary_info'] = house_sel.css('.address>.houseInfo::text').get()
                house['summary_total_price'] = house_sel.css('.priceInfo .totalPrice span::text').get()
                house['summary_unit_price'] = house_sel.css('.priceInfo .unitPrice span::text').get()
                house['get_detailed'] = False
                house['page_url'] = url
                records.append(house)
                # for k,v in house.items(): print('{}: {}'.format(k,v)) 
                # print('')
            if mongo_house_summary_col is not None:
                mongo_house_summary_col.insert_many(records)
            if save_txt_path is not None:
                if not os.path.exists(os.path.dirname(save_txt_path)): os.makedirs(os.path.dirname(save_txt_path))
                with open(save_txt_path, 'a', encoding='utf-8') as f:
                    for house in records:
                        f.write(str(house) + '\n')
        else:
            print('Can not get house urls and summary info due to failure to get response')
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('\n'+'='*60)
        print('Error type: {}, happended in line {}'.format(exc_type, exc_tb.tb_lineno))
        print('Detailed info of the above error: {}'.format(e))
        print('='*60+'\n')
        raise RuntimeError(e)
    return records
    
def get_all_house_urls(mongo_page_url_col, mongo_house_summary_col=None, save_txt_path=None, proxies={}, from_scratch=False):
    page_url_objs = list(mongo_page_url_col.find())
    if from_scratch:
        unfinished_page_urls = [url_obj['url'] for url_obj in page_url_objs]
    else:
        unfinished_page_urls = [url_obj['url'] for url_obj in page_url_objs if not url_obj['finished']]
    for page_url in unfinished_page_urls:
        retry, success = 0, False
        while retry < 20:
            try:
                get_house_url_and_summary_info(page_url, mongo_house_summary_col, save_txt_path, proxies)
                mongo_page_url_col.update_one({'url':page_url}, {'$set': {'finished': True}})
                success = True
                break
            except Exception as e:
                print('Fail to get house urls from {}, retry = {}'.format(page_url, retry))
                print('Detailed info of the above error: {}'.format(e))
                retry += 1
                time.sleep(0.2)
        if not success: 
            print('\n!!!Fail to get house urls from {} AFTER {} retry, please check db.\n'.format(page_url, retry))


def get_house_detailed_info(url, mongo_house_detailed_col, mongo_block_col, mongo_house_summary_col=None, proxies={}, print_flag=False):  
    try:
        if len(list(mongo_house_detailed_col.find({'url': url}))) > 0:
            print('Warning: Duplicated case detected, url = {}'.format(url))
            return {}
        # print_flag = True
        if print_flag: print('\nhouse detailed info processing: ', url)
        headers = {'User-Agent': ua}  
        if not proxies:
            time.sleep(random.uniform(0.5,1.0))
            res = requests.get(url, headers=headers)
        else:
            if print_flag: print('using proxies: {}'.format(proxies))
            res = requests.get(url, headers=headers, proxies=proxies)
        house = {}
        # with try...except... outside for IP proxy, here we can ask for a 200 status code
        if proxies: assert res.status_code == 200
        if res.status_code == 200:
            sel = parsel.Selector(res.text)
            base_sel = sel.css('.m-content .base .content')
            trans_sel = sel.css('.m-content .transaction .content')
            house['url'] = url
            if mongo_house_summary_col is not None:
                try:
                    house_summary = mongo_house_summary_col.find_one({'url': url})
                    for key in ['title', 'summary_info', 'summary_total_price', 'summary_unit_price']:
                        house[key] = house_summary[key]
                except:
                    print('Error: Failed to get summary info for url: {}'.format(url))
            # get price: 2 different types
            price1 = sel.css('div.priceBox span::text').get()
            if len(sel.css('div.priceBox span::text')) > 0:
                unit_price1 = sel.css('div.priceBox span::text')[1].get()
            else:
                unit_price1 = None
            price2_value = sel.css('.overview .price span.total::text').get()
            price2_unit = sel.css('.overview .price span.unit span::text').get()
            unit_price2_value = sel.css('.overview .price span.unitPriceValue::text').get()
            unit_price2_unit = sel.css('.overview .price span.unitPriceValue i::text').get()
            if type(price2_value) is str and type(price2_unit) is str:
                price2 = price2_value + price2_unit
            else:
                price2 = price2_value
            if type(unit_price2_value) is str and type(unit_price2_unit) is str:
                unit_price2 = unit_price2_value + unit_price2_unit
            else:
                unit_price2 = unit_price2_value
            house['price'] = price2 if price2 is not None else price1
            house['unit_price'] = unit_price2 if unit_price2 is not None else unit_price1
            house['layout'] = base_sel.xpath('//li/span[text()="房屋户型"]/parent::li/text()').get()
            house['floor'] = base_sel.xpath('//li/span[text()="所在楼层"]/parent::li/text()').get()
            house['fa'] = base_sel.xpath('//li/span[text()="建筑面积"]/parent::li/text()').get()
            house['v_struct'] = base_sel.xpath('//li/span[text()="户型结构"]/parent::li/text()').get()
            house['area_in'] = base_sel.xpath('//li/span[text()="套内面积"]/parent::li/text()').get()
            house['bldg_type'] = base_sel.xpath('//li/span[text()="建筑类型"]/parent::li/text()').get()
            house['orient'] = base_sel.xpath('//li/span[text()="房屋朝向"]/parent::li/text()').get()
            house['bldg_struct'] = base_sel.xpath('//li/span[text()="建筑结构"]/parent::li/text()').get()
            house['decorat'] = base_sel.xpath('//li/span[text()="装修情况"]/parent::li/text()').get()
            house['ele_ratio'] = base_sel.xpath('//li/span[text()="梯户比例"]/parent::li/text()').get()
            house['ele'] = base_sel.xpath('//li/span[text()="配备电梯"]/parent::li/text()').get()
            house['market_time'] = trans_sel.xpath('//li/span[text()="挂牌时间"]/following-sibling::span/text()').get()
            house['last_trade_time'] = trans_sel.xpath('//li/span[text()="上次交易"]/following-sibling::span/text()').get()
            house['years'] = trans_sel.xpath('//li/span[text()="房屋年限"]/following-sibling::span/text()').get()
            house['ass_id'] = trans_sel.xpath('//li/span[text()="房协编码"]/following-sibling::span/text()').get()
            house['ownership_type'] = trans_sel.xpath('//li/span[text()="交易权属"]/following-sibling::span/text()').get()
            house['usage_type'] = trans_sel.xpath('//li/span[text()="房屋用途"]/following-sibling::span/text()').get()
            house['property_right'] = trans_sel.xpath('//li/span[text()="产权所属"]/following-sibling::span/text()').get()
            layout_detailed = sel.css('#layout #infoList .row')
            house['layout_detailed'] = [
                {   
                    'name': row.css('.col::text')[0].get(), 
                    'area': row.css('.col::text')[1].get(),
                    'orient': row.css('.col::text')[2].get(),
                    'window': row.css('.col::text')[3].get()
                } for row in layout_detailed
            ]
            block_id = sel.css('.aroundInfo').xpath(
                    '//span[text()="小区名称"]/following-sibling::a[@class="info "]/@href'
                ).get()
            block_id = re.compile('\/xiaoqu\/([0-9]+)\/').findall(block_id)
            if len(block_id) == 1:
                tmp = list(mongo_block_col.find({'id': block_id[0]}))
                if len(tmp) > 0:
                    assert len(tmp) == 1
                    block_info = tmp[0]
                else:
                    block_info = get_block_info(block_id[0], mongo_block_col, proxies)
            else:
                print('Cannot find block id and thus no block info is available for house {} at {}'.format(ouse['ass_id'],url))
                block_info = {} 
            if 'coord_lng' in block_info:
                house['coord_lng'], house['coord_lat'] = block_info['coord_lng'], block_info['coord_lat']
            if 'bldg_year' in block_info:
                house['bldg_year'] = block_info['bldg_year']
            house['block_info'] = block_info
            if print_flag:
                for k, v in house.items(): print('{}: {}'.format(k,v))
            mongo_house_detailed_col.insert_one(house)
        else:
            print('House detailed info not found as failed to get response')
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('\n'+'='*60)
        print('Error type: {}, happended in line {}'.format(exc_type, exc_tb.tb_lineno))
        print('Detailed info of the above error: {}'.format(e))
        print('='*60+'\n')
        raise RuntimeError(e)
    return house
    
def get_block_info(idx, mongo_block_col=None, proxies={}):
    # t0 = time.time()
    try:
        url = 'https://sz.lianjia.com/xiaoqu/{}/'.format(idx)
        headers = {'User-Agent': ua}  
        if not proxies:
            time.sleep(random.uniform(0.5,1.0))
            res = requests.get(url, headers=headers)
        else:
            res = requests.get(url, headers=headers, proxies=proxies)
        block = {}
        # t1 = time.time()
        if proxies: assert res.status_code == 200
        if res.status_code == 200:
            sel = parsel.Selector(res.text)
            block['id'] = idx
            block['url'] = url
            block['name'] = sel.css('.detailTitle::text').get()
            block['address'] = sel.css('.detailDesc::text').get()
            block['unit_price'] = sel.css('.xiaoquUnitPrice::text').get()
            block['built_year'] = sel.xpath('//span[text()="建筑年代"]/following-sibling::span/text()').get()
            block['management_fee'] = sel.xpath('//span[text()="物业费用"]/following-sibling::span/text()').get()
            block['bldg_num'] = sel.xpath('//span[text()="楼栋总数"]/following-sibling::span/text()').get()
            block['house_num'] = sel.xpath('//span[text()="房屋总数"]/following-sibling::span/text()').get()
            coords = sel.re('resblockPosition:\'([0-9\.]*),([0-9\.]*)\',')
            if len(coords) == 2:
                block['coord_lng'], block['coord_lat'] = coords
            else:
                print('Invalid coords: {}'.format(coords))
                block['coord_lng'], block['coord_lat'] = None, None
            # for k,v in block.items(): print('{}: {}'.format(k,v))
            # t2 = time.time()
            # print('\nGetting response takes: {:4.4}s, Parsering takes: {:4.4}s'.format(t1-t0, t2-t1))
            
        else:
            print('Block info not found as failed to get response')
        if len(block)>0 and mongo_block_col is not None:
            mongo_block_col.insert_one(block)
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print('\n'+'='*60)
        print('Error type: {}, happended in line {}'.format(exc_type, exc_tb.tb_lineno))
        print('Detailed info of the above error: {}'.format(e))
        print('='*60+'\n')
        raise RuntimeError(e)
    return block
    

def get_all_house_detailed_info(mongo_house_summary_col, mongo_house_detailed_col, mongo_block_col, proxies={}):
    t0 = time.time()
    house_summary_objs = list(mongo_house_summary_col.find())
    unfinished_house_urls = [house_obj['url'] for house_obj in house_summary_objs if not house_obj['get_detailed']]
    num = len(unfinished_house_urls)
    count_idx = 0
    count_idx_already_processed = 0
    for house_url in unfinished_house_urls:
        # in case that mongo_house_summary_col is renewed and some url are set as get_detailed=False by default but actually 
        # already processed for fetching detailed info
        if len(list(mongo_house_detailed_col.find({'url': house_url}))) > 0:
            mongo_house_summary_col.update_one({'url': house_url}, {'$set': {'get_detailed': True}})
            count_idx_already_processed += 1
            count_idx += 1
            print('This record has been process and exists in mongo_house_detailed_col, count = {}'.format(count_idx_already_processed))
            continue
        retry, success = 0, False
        if count_idx % 100 == 0: 
            t1 = time.time()
            print('\n\nProcessing house detailed info: {} of {} ({:4.2f}%), time cost of last batch: {:4.4f}s'.format(
                count_idx, num, count_idx/num*100, t1-t0))
            t0 = t1
        while retry < 20:
            try:
                if retry>0: print('retry = {}'.format(retry))
                get_house_detailed_info(house_url, mongo_house_detailed_col, mongo_block_col, mongo_house_summary_col, proxies)
                mongo_house_summary_col.update_one({'url': house_url}, {'$set': {'get_detailed': True}})
                success = True
                break
            except Exception as e:
                print('Fail to get house detailed info from {}, retry = {}'.format(house_url, retry))
                print('Detailed info of the above error: {}'.format(e))
                retry += 1
                time.sleep(0.2)
        if success:
            count_idx += 1
        else:
            print('\n!!!Fail to get house detailed info from {} AFTER {} retry, please check db.\n'.format(house_url, retry))
    
# def fix_null_price_for_house_detailed_record(mongo_house_detailed_col, proxies={}):
    # headers = {'User-Agent': ua}  
    # null_price_records = list(mongo_house_detailed_col.find({'price': None}))
    # for record in null_price_records:
        # this_url = record['url']
        # time.sleep(random.uniform(0.5,1.0))
        # if not proxies:
            # res = requests.get(this_url, headers=headers)
        # else:
            # res = requests.get(this_url, headers=headers, proxies=proxies)
        # if proxies: assert res.status_code == 200
        # if res.status_code == 200:
            # sel = parsel.Selector(res.text)
            # price = sel.css('.overview .price span.total::text').get()
            # unit_price = sel.css('.overview .price span.total::text')
            
    

def main():
    
    #====================================#
    #      Below Argument Setting        #
    #====================================#
    task = 'yantian'
    
    # ip proxy arguments
    # tunnel = "tps133.kdlapi.com:15818"
    username = None
    password = None
    tunnel = None
    
    if task == 'futian':
        db_name = 'L3_SZ_CityScope'
        page_url_collection_name = 'page_url_second_hand_lianjia_futian'
        block_collection_name = "block_lianjia_futian"
        house_summary_collection_name = "house_summary_second_hand_lianjia_futian"
        house_detailed_collection_name = 'house_detailed_second_hand_lianjia_futian'
        
        url_list = [{
                        'name':'福田区塔楼', 'count': 2731, 'max_page': 92,
                        'url': 'https://sz.lianjia.com/ershoufang/futianqu/bt1/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/futianqu/pg{}bt1/'
                    },{
                        'name':'福田区板楼', 'count': 839, 'max_page': 28,
                        'url': 'https://sz.lianjia.com/ershoufang/futianqu/bt2/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/futianqu/pg{}bt2/'
                    },{
                        'name':'福田区板塔结合二室及以下', 'count': 1635, 'max_page': 55,
                        'url': 'https://sz.lianjia.com/ershoufang/futianqu/bt3l1l2/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/futianqu/pg{}bt3l1l2/'
                    },
                    {
                        'name':'福田区板塔结合二室以上', 'count': 1470, 'max_page': 49,
                        'url': 'https://sz.lianjia.com/ershoufang/futianqu/bt3l3l4l5l6/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/futianqu/pg{}bt3l3l4l5l6/'
                    }]
                
    if task == 'nanshan':
        db_name = 'L3_SZ_CityScope'
        page_url_collection_name = 'page_url_second_hand_lianjia_nanshan'
        block_collection_name = "block_lianjia_nanshan"
        house_summary_collection_name = "house_summary_second_hand_lianjia_nanshan"
        house_detailed_collection_name = 'house_detailed_second_hand_lianjia_nanshan'
        
        url_list = [{
                        'name':'南山区塔楼', 'count': 2736, 'max_page': 92,
                        'url': 'https://sz.lianjia.com/ershoufang/nanshanqu/bt1/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/nanshanqu/pg{}bt1/'
                    },{
                        'name':'南山区板楼', 'count': 1011, 'max_page': 34,
                        'url': 'https://sz.lianjia.com/ershoufang/nanshanqu/bt2/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/nanshanqu/pg{}bt2/'
                    },{
                        'name':'南山区板塔结合', 'count': 2177, 'max_page': 73,
                        'url': 'https://sz.lianjia.com/ershoufang/nanshanqu/bt3/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/nanshanqu/pg{}bt3/'
                    }]
                    
    if task == 'luohu':
        db_name = 'L3_SZ_CityScope'
        page_url_collection_name = 'page_url_second_hand_lianjia_luohu'
        block_collection_name = "block_lianjia_luohu"
        house_summary_collection_name = "house_summary_second_hand_lianjia_luohu"
        house_detailed_collection_name = 'house_detailed_second_hand_lianjia_luohu'
        
        url_list = [{
                        'name':'罗湖区塔楼', 'count': 2128, 'max_page': 71,
                        'url': 'https://sz.lianjia.com/ershoufang/luohuqu/bt1/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/luohuqu/pg{}bt1/'
                    },{
                        'name':'罗湖区板楼', 'count': 604, 'max_page': 21,
                        'url': 'https://sz.lianjia.com/ershoufang/luohuqu/bt2/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/luohuqu/pg{}bt2/'
                    },{
                        'name':'罗湖区板塔结合二室及以下', 'count': 2242, 'max_page': 75,
                        'url': 'https://sz.lianjia.com/ershoufang/luohuqu/bt3l1l2//',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/luohuqu/pg{}bt3l1l2/'
                    },
                    {
                        'name':'罗湖区板塔结合二室以上', 'count': 1150, 'max_page': 39,
                        'url': 'https://sz.lianjia.com/ershoufang/luohuqu/bt3l3l4l5l6/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/luohuqu/pg{}bt3l3l4l5l6/'
                    }]
                    
    if task == 'longhua':
        db_name = 'L3_SZ_CityScope'
        page_url_collection_name = 'page_url_second_hand_lianjia_longhua'
        block_collection_name = "block_lianjia_longhua"
        house_summary_collection_name = "house_summary_second_hand_lianjia_longhua"
        house_detailed_collection_name = 'house_detailed_second_hand_lianjia_longhua'
        
        url_list = [{
                        'name':'龙华区塔楼', 'count': 1251, 'max_page': 42,
                        'url': 'https://sz.lianjia.com/ershoufang/longhuaqu/bt1/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/longhuaqu/pg{}bt1/'
                    },{
                        'name':'龙华区板楼', 'count': 849, 'max_page': 29,
                        'url': 'https://sz.lianjia.com/ershoufang/longhuaqu/bt2/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/longhuaqu/pg{}bt2/'
                    },{
                        'name':'龙华区板塔结合', 'count': 2197, 'max_page': 74,
                        'url': 'https://sz.lianjia.com/ershoufang/longhuaqu/bt3/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/longhuaqu/pg{}bt3/'
                    }]
                    
    if task == 'baoan':
        db_name = 'L3_SZ_CityScope'
        page_url_collection_name = 'page_url_second_hand_lianjia_baoan'
        block_collection_name = "block_lianjia_baoan"
        house_summary_collection_name = "house_summary_second_hand_lianjia_baoan"
        house_detailed_collection_name = 'house_detailed_second_hand_lianjia_baoan'
        
        url_list = [{
                        'name':'宝安区塔楼', 'count': 1315, 'max_page': 44,
                        'url': 'https://sz.lianjia.com/ershoufang/baoanqu/bt1/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/baoanqu/pg{}bt1/'
                    },{
                        'name':'宝安区板楼', 'count': 652, 'max_page': 22,
                        'url': 'https://sz.lianjia.com/ershoufang/baoanqu/bt2/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/baoanqu/pg{}bt2/'
                    },{
                        'name':'宝安区板塔结合', 'count': 2839, 'max_page': 95,
                        'url': 'https://sz.lianjia.com/ershoufang/baoanqu/bt3/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/baoanqu/pg{}bt3/'
                    }]
                    
    if task == 'longgang':
        db_name = 'L3_SZ_CityScope'
        page_url_collection_name = 'page_url_second_hand_lianjia_longgang'
        block_collection_name = "block_lianjia_longgang"
        house_summary_collection_name = "house_summary_second_hand_lianjia_longgang"
        house_detailed_collection_name = 'house_detailed_second_hand_lianjia_longgang'
        
        url_list = [{
                        'name':'龙岗区塔楼二室及以下', 'count': 1386, 'max_page': 47,
                        'url': 'https://sz.lianjia.com/ershoufang/longgangqu/bt1l1l2/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/longgangqu/pg{}bt1l1l2/'
                    },{
                        'name':'龙岗区塔楼二室以上', 'count': 2110, 'max_page': 71,
                        'url': 'https://sz.lianjia.com/ershoufang/longgangqu/bt1l3l4l5l6/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/longgangqu/pg{}bt1l3l4l5l6/'
                    },{
                        'name':'龙岗区板楼', 'count': 2600, 'max_page': 87,
                        'url': 'https://sz.lianjia.com/ershoufang/longgangqu/bt2/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/longgangqu/pg{}bt2/'
                    },{
                        'name':'龙岗区板塔结合二室及以下', 'count': 2564, 'max_page': 86,
                        'url': 'https://sz.lianjia.com/ershoufang/longgangqu/bt3l1l2/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/longgangqu/pg{}bt3l1l2/'
                    },{
                        'name':'龙岗区板塔结合三室', 'count': 2428, 'max_page': 81,
                        'url': 'https://sz.lianjia.com/ershoufang/longgangqu/bt3l3/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/longgangqu/pg{}bt3l3/'
                    },{
                        'name':'龙岗区板塔结合三室以上', 'count': 1544, 'max_page': 52,
                        'url': 'https://sz.lianjia.com/ershoufang/longgangqu/bt3l4l5l6/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/longgangqu/pg{}bt3l4l5l6/'
                    }]
                    
    if task == 'yantian':
        db_name = 'L3_SZ_CityScope'
        page_url_collection_name = 'page_url_second_hand_lianjia_yantian'
        block_collection_name = "block_lianjia_yantian"
        house_summary_collection_name = "house_summary_second_hand_lianjia_yantian"
        house_detailed_collection_name = 'house_detailed_second_hand_lianjia_yantian'
        
        url_list = [{
                        'name':'盐田区', 'count': 1638, 'max_page': 55,
                        'url': 'https://sz.lianjia.com/ershoufang/yantianqu/',
                        'formatted_url': 'https://sz.lianjia.com/ershoufang/yantianqu/pg{}/'
                    }]
    #====================================#
    #      Above Argument Setting        #
    #====================================#
    
    # start mongodb
    client = pymongo.MongoClient('localhost', 27017)  
    db = client[db_name]      
    page_url_col = db[page_url_collection_name]
    block_col = db[block_collection_name]    
    house_summary_col = db[house_summary_collection_name]
    house_detailed_col = db[house_detailed_collection_name]
    
    # config ip proxy
    if tunnel is None and (username is None or password is None):
        proxies = {}
    elif tunnel is not None:
        proxies = {
            "http": "http://%(proxy)s/" % {"proxy": tunnel},
            "https": "http://%(proxy)s/" % {"proxy": tunnel}
        }
    elif username is not None and password is not None:
        proxies = {
            "http": "http://%(user)s:%(pwd)s@%(proxy)s/" % {"user": username, "pwd": password, "proxy": tunnel},
            "https": "http://%(user)s:%(pwd)s@%(proxy)s/" % {"user": username, "pwd": password, "proxy": tunnel}
        }
    if proxies: print('Using IP proxy...\n', proxies)
    
    
    # get all page urls: do it only once, very little chance to be interrupted 
    if page_url_col.count_documents({}) > 100:
        pass
    else:
        get_all_page_urls(url_list, page_url_col)
        print('Get all page urls for task: {}'.format(task))
    
    
    # get all house urls (and summary info) from page urls
    # get_all_house_urls(page_url_col, house_summary_col, proxies=proxies, from_scratch=True)
    get_all_house_urls(page_url_col, house_summary_col, proxies=proxies)
    
    
    # get all house detailed info
    print('Starting get_all_house_detailed_info...')
    get_all_house_detailed_info(house_summary_col, house_detailed_col, block_col, proxies)
    
  
    
def test1():
    url = 'https://sz.lianjia.com/ershoufang/futianqu/pg92bt1/'
    url = 'https://sz.lianjia.com/ershoufang/futianqu/pg35bt1/'
    records = get_house_url_and_summary_info(url)
    for r in records:
        print('\n{}\n{}'.format(r['title'], r['url']))

if __name__ == "__main__":
    # test1()
    main()