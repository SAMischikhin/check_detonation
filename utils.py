import re
from math import floor, pow, log10
from decimal import *
import numpy as np

"""проверка условия для df"""
def check_conditions_for(phenomenon, df):
    return bool(sum(df[(phenomenon, 'is')].tolist()))


""" Арифметика """
def nearest(lst, target): # list, float -> float
    """ближайший компонент массива"""
    return min(lst, key=lambda x: abs(x-target))

def round_sig(x): #float [x<1] -> float or None
    """округление вверх до 1 значащей цифры числел меньше 1"""
    if x >= 1:
        return None
    else:
        rd=-int(floor(log10(abs(x)))) # позиция значащей цифры х
        return float(Decimal(x).quantize(Decimal('.'+'0'*rd), rounding=ROUND_UP))
    
def sum_values_by_index(values_list, index_list):
    return sum([float(values_list[i]) for i in index_list])


""" Гетеры """
def get_key(d, search_value): #[{key: list_value}] -> key if search value in list_value
    for key, list_value in d.items():
        if str(search_value) in list_value:
            return key
    return None

def get_rooms(rooms_dict, box_list):
    res_dict = {}
    for box in box_list:
        key = get_key(rooms_dict, box)
        if key not in res_dict.keys():
            res_dict[key] = []
        res_dict[key].append(box)
        
    return (res_dict)

def get_box_number(box_name): #str -> int
    """ номер бокса по названию столбца в выходном файле limits"""
    reg_exp ='Box_([0-9]{3})'
    return int(re.match(reg_exp, box_name).groups()[0])
        

""" Работа с инпут-файлами """
def get_input_files(input_dir_list, required_input_file_names): # list, list -> dict or None
    """возвращает имена требуемых инпут-файлов, или None, если нет хотя бы одного,
    возвращвется словарь: ключ: имя; значение: имя с расширением из input dir """
    input_dir_list_name = [a.split('.')[0] for a in input_dir_list]
    
    if set(required_input_file_names) <= set(input_dir_list_name):
        return {a.split('.')[0]: a for a in input_dir_list if a.split('.')[0] in required_input_file_names}

"""Работа с BXDATA"""    
def get_volumes_from_BXDATA(path): #--> list, all volumes by boxes
    BXDATA = open(path)
    for line in BXDATA:
        if line.strip().startswith('Volume'):
            BXDATA.readline()
            volumes_str = BXDATA.readline()
            return volumes_str.strip().split()
        
def sum_volumes_by_number(number_list, bxdata_path):
    values_list = get_volumes_from_BXDATA(bxdata_path)
    index_list = [a-1 for a in number_list]
    return sum_values_by_index(values_list, index_list)

def write_L_for_LIMITS(bxdata_path):
    # BXDATA находится в solve\data, но может иметь любое расширение 
    volumes = get_volumes_from_BXDATA(bxdata_path)
    if volumes == None:
        return False
    else:
        # в той же директории, что и BXDATA
        char_dim_path = bxdata_path.replace(bxdata_path.split('\\')[-1], 'L.txt')

        outFile = open(char_dim_path,'w')
        outFile.write('\t'.join([str(round(pow(float(a),1/3),5)) for a in volumes]))
        outFile.close()
        return True    


""" Работа с pandas"""
def get_boxes_by_phenomenon(columns_with_box_data, phenomenon): # pandas.DataFrame, str -> list(str), str like "Boxes_XXX"
    if phenomenon == 'deflagration':
        replaceable = [0,3]
    if phenomenon == 'detonation':
        replaceable = [0,1]
    return columns_with_box_data.replace(replaceable, np.nan).dropna(how="all").index.tolist()
 
def get_boxes_number_by_phenomenon(columns_with_box_data, phenomenon): # pandas.DataFrame, str -> list(int)
    list_boxes_names = get_boxes_by_phenomenon(columns_with_box_data, phenomenon)
    return list(map(lambda box_name: get_box_number(box_name), list_boxes_names))
 
def split_row_by_rooms(tag_row, boxes_key, rooms_key): #pandas.core.series.Series -> list(dict))
    res = []
    for i, room in enumerate(tag_row[rooms_key]):
        row = tag_row.copy()
        row[boxes_key] = row[boxes_key][i]#re.compile(reg_exp).findall(row['Boxes'][0])[i]
        row[rooms_key] = row[rooms_key][i]
        res.append(row)
    return res


""" декоратор, обрабатывающий PermissionDeniedError"""  
def permission_err_decorator(func):
    reg_exp ='(\[.*\])* (.*): (.*)' 
    def wrapper(*args):
        try:
            return func(*args)
        except PermissionError as e:
            massage_list = re.match(reg_exp, str(e)).groups()
            return myError.send('File {} is open. {}. Close the file'.format(massage_list[2], massage_list[1]))
    return wrapper    