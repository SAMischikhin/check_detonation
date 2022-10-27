import os
import time
import pandas as pd
import configparser
from subprocess import PIPE, Popen
import warnings
import shutil
from messages import MyParsingError
from utils import get_input_files, write_L_for_LIMITS, permission_err_decorator, sum_volumes_by_number
import ploting
from solve import Solve

"""Константы"""
"""требуемый входной набор (имена файлов)"""
REQUIRED_INPUT_FILE_NAMES = ("C_H2", "C_O2", "C_v", "p", "t", "BXDATA")

"""отключение FutureWarnings. Оно касается указания на старую версию конвертора в excel"""
warnings.filterwarnings("ignore", category=FutureWarning)
 
""" Создание объекта решения задачи"""
solve = Solve()

"""Чтение конфиг-файла"""
config = configparser.ConfigParser(
    converters={'list': lambda x: [i.strip() for i in x.split(',')],
                })
try:
    config.read("config.ini", encoding="utf-8-sig")
    solve.myInfo.send('config.ini is readed')
except configparser.Error:
    raise MyParsingError("config.ini", solve.logger)

"""проверка наличия директории с исходными данными (input_dir)"""
try:
    input_dir_list = os.listdir(config["general"]["INPUT_DIR_PATH"])
except:
    solve.myError.send("INPUT DIRECTORY DO NOT FOUND")

"""получение перечня файлов из input_dir, соответствующих требуемым именам"""
input_dir_dict_comp = get_input_files(input_dir_list, REQUIRED_INPUT_FILE_NAMES)

"""проверка наличия всех требуемых файлов в директории входных данных"""
if  input_dir_dict_comp == None:
    solve.myError.send(u"{} files should be in input directory".format(', '.join(REQUIRED_INPUT_FILE_NAMES)))

""" Копироание файлов из папки с данными в рабочую папку """
solve.myInfo.send('Copying required input files from {}'.format(config["general"]["INPUT_DIR_PATH"]))

for f_name in input_dir_dict_comp.values():
    try:
        input_file = '{}\\{}'.format(config["general"]["INPUT_DIR_PATH"], f_name)
        target_file ='{}\\{}\\{}'.format(solve.solve_path, 'data', f_name)
        shutil.copyfile(input_file, target_file)
        solve.myInfo.send("---> {} is copied".format(f_name))
    
    except FileNotFoundError:
        solve.myError.send("xxxxX {} is not copied. Try again".format(f_name))

""" Путь bxdata удобнее иметь в общем доступе """
bxdata_path = '{}\\{}\\{}'.format(solve.solve_path, 'data', input_dir_dict_comp.pop('BXDATA'))
# метод .pop() удаляет ключ после извлечения значения

"""запись файла характерных размеров (инпут для LIMITS)"""
if write_L_for_LIMITS(bxdata_path):
    solve.myInfo.send('char. dimentions file L.txt is generated')
else:
    solve.myError.send('BXDATA file reading Error. Char. dimentions file L.txt is not generated')

"""Запуск LIMITS"""
limits_file = config["general"]["limits_exec"]

"""копирования исполняемого файла limits в ".\solve\data"
необходимо запускать его в папке с исходными данными"""
try:
    shutil.copyfile(limits_file, "{}\\{}\\{}".format(solve.solve_path, 'data', limits_file))
except FileNotFoundError:
    solve.myError.send('There is no {} (specified in config.ini) in working dir'.format(limits_file))

"""переход ".\solve\data" """
os.chdir('{}\\{}'.format(solve.solve_path, 'data'))

"""запуск файла и вывод ошибки Limits при наличии"""
try:
    with Popen(limits_file, stdout=PIPE, stderr=PIPE, shell=True) as process:
        error = process.communicate()[1]
        
    if error == b'':
        solve.myInfo.send('{} completed successfully'.format(limits_file))
    else:
        solve.myError.send('{} error!\n {}'.format(limits_file, str(error).split('\\r\\r\\n')[0]))
            
except FileNotFoundError:
    solve.myError.send("{} was specified in config.ini but was not found in working directory".format(config["general"]["limits_exec"]))

""" удаление копии файла limits в ".\solve\data" """
os.remove('{}\\{}\\{}'.format(solve.solve_path, 'data', limits_file))

"""название файла с результатами анализа LIMITS"""
LIMITS_RES_FILE = "regims.txt"

"""словарь обозначений LIMITS для горения и детонации"""
LIMITS_KEYS_DICT = {y[0]:int(y[1]) for y in config.items('limits_key')}

""" Создание первого dataframe (для отрисовки диаграмм)"""
solve.create_first_dataframe(LIMITS_RES_FILE, LIMITS_KEYS_DICT)

""" Вырезание времени стационара расчета """
solve.stacionar_cut(float(config['general']['stacionar_time']))

"""Проверка наличия условий для дефлаграции и детонации"""
solve.phenomena_analysis(bxdata_path)
        
"""Запись файла, содержащего колонки данных для отрисовки диаграмм;
файл не используется непосредственно для отрисовки, он резервирует информацию"""
df_source_to_excel = permission_err_decorator(solve.df_source.to_excel)
df_source_to_excel('{}\\{}\\{}'.format(solve.solve_path, 'results', 'pictures_data_copy.xls'))
solve.myInfo.send('{} is saved'.format('pictures_data_copy.xls'))

"""Отрисовка диаграмм"""
try:
    """ если не возникает условий ни для горения, ни для детонации
    - диаграмма с барами, пропорциональными объему не имеет смысла""" 
    if solve.existing_phenomena == []:
        picture = ploting.PlotDetonationOne(config)
        
    else:
        solve.myInfo.send('ploting with config.dif_bars={} is starting'.format(config.getboolean("picture","dif_bars")))
    
        if not config.getboolean("picture","dif_bars"):
            picture = ploting.PlotDetonationOne(config)
   
        if config.getboolean("picture","dif_bars"):
            picture = ploting.PlotDetonationTwo(config)
    
    """ Отрисовка """
    picture.plot(solve)
    solve.myInfo.send('ploting is completed')
        
except configparser.Error:
    raise MyParsingError("config.ini")

solve.myInfo.send('Analysis by rooms (boxes group) is started. Additional xlsx files will be created in working directory')

for phenomenon in solve.existing_phenomena:
    solve.myInfo.send('Analysis conditions for {} is started'.format(phenomenon))
    """ собираем новый датафрейм. Теперь анализ пойдет по помещениям внутри каждого временного слоя"""
    solve.create_second_dataframe(config, phenomenon)
    
    """ Происходит назначение индекса временного слоя. Новый временной слой начинается, если меняется
    состав помещений, в которых возникают условия для горения/детонации """
    solve.index_by_time()

    """ Добавление слоев по помещениям """
    solve.split_by_rooms_layers()
    
    """ Агрегирующие функции """
    """ индексы всех боксов за временной срез """
    lambda_AllBoxes = lambda s: sorted(list(set([i for j in s for i in j])))
    lambda_AllBoxes.__name__ = 'boxes_numbers'
    
    def volumes_count(s):
        """подсчет общего объема, где возможен процесс(горение/детонация)"""
        number_list = lambda_AllBoxes(s)
        return sum_volumes_by_number(number_list, bxdata_path)
    
    """ Перечень агрегирующих функций с указанием колонок для их применения """
    agg_func_selection = {'Time': ['idxmin','idxmax'], 'rooms': 'first',
                          "Boxes": [lambda_AllBoxes, volumes_count]}
    
    """ Агрегирование и группировка """
    solve.groupby(["time_index","rooms"], agg_func_selection)

    """ Добавление информациии """
    """ Времена """
    solve.add_times_data()

    """ Концентрации """
    """ чтение файлов """
    conc_dict = {} # словарь dataframes концентраций, ключ - имя файла без расширения
    for filename in input_dir_dict_comp:
        conc_dict[filename] = pd.read_fwf(input_dir_dict_comp[filename])
    
    """ добавление информации """
    solve.add_concentration_data(conc_dict)
    
    """Запись в файл"""
    """на вывод в файл отправляем только следующие столбцы (с их подстолбцами)"""
    df_to_excel = permission_err_decorator(solve.df[['Time_interval','Boxes','Concentration']].to_excel)
    df_to_excel('{}\\{}\\{}_out.xls'.format(solve.solve_path, 'results', phenomenon))
    solve.myInfo.send('{}_out.xls is saved'.format(phenomenon))
    
solve.myInfo.send('Analysis by rooms (boxes group) is completed')
solve.myInfo.send('Program is finished successfully')

time.sleep(5)
exit()