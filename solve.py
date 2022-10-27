import os
import pandas as pd
from utils import check_conditions_for, sum_volumes_by_number 
from utils import get_boxes_number_by_phenomenon, get_rooms,  split_row_by_rooms
from messages import MyInfo, MyError
from app_logger import get_logger
from time_index import TimeIndex

class Solve():
    def __init__(self):
        """перечень феноменов для анализа"""
        self.phenomena_for_analysis = ['deflagration', 'detonation']
        self.existing_phenomena = [] #пока не проанализировали - пусто
        """путь к директории решения"""
        self.solve_path = self._get_solve_dir()

        """pandas.DataFrame"""
        self.df_source = None
        self.df = None
        """Создание логера """
        self.logger = get_logger("{}\\{}".format(self.solve_path, "log.log"))

        """Создание сообщений """
        self.myInfo = MyInfo(self.logger)
        self.myError = MyError(self.logger)
        
        self.myInfo.send('Program is started')
    
    @staticmethod
    def _get_time_or_end_calc(time_list, index):
        try:
            return time_list[index]
        except KeyError as e:
            return 'end calc'
    
    @staticmethod        
    def _get_solve_dir():    
        """ созданиt новых каталогов для каждого запуска скрипта"""
        workdir_path = os.getcwd()
        solve_path = None
        i = 0
        while 1:
            solve_path = '{}\\solve\\{}'.format(workdir_path, i)
            try:
                os.chdir(solve_path)
                """Переход в корневую папку"""
                os.chdir('..\\')
                os.chdir('..\\')
                i += 1
            except FileNotFoundError:
                os.makedirs('{}\\{}'.format(solve_path, 'data'))
                os.makedirs('{}\\{}'.format(solve_path, 'results'))
                return solve_path
    
    def create_first_dataframe(self, limits_filename, limits_keys_dict):
        """df_source - исходный dataframe, в него выгружается файл LIMITS_RES_FILE
        файл/dataframe имеет следующую структуру:
        Time            Box_001   Box_002   ... Box_N
        float(time_0)     int       int          int
        ...
        float(time_M)     int       int          int
        где int in (0,1,3) - нет, возможно горение, возможна детонация""" 
        
        limits_filename_path = '{}\\{}\\{}'.format(self.solve_path, "data", limits_filename)
        
        self.df_source = pd.read_csv(limits_filename_path, sep=' ')
        self.myInfo.send('{} is readed'.format(limits_filename))
     
        """удаление лишней колонки dataframe индексы: 'Time, Box_001 ... Box_NNN"""
        self.df_source = self.df_source.drop(columns='Unnamed: 0')
        
        """определение булевых переменных: есть ли горение/детонация хоть в одном боксе на данном шаге по времени"""
        for phenomenon in self.phenomena_for_analysis:
            self.df_source[(phenomenon, 'is')] = self.df_source.iloc[:, 1:].isin([limits_keys_dict[phenomenon]]).T.any()

    def stacionar_cut(self, stacionar_time):
        self.df_source['Time'] -= stacionar_time
        self.df_source = self.df_source.loc[self.df_source['Time'] >= 0][:]
        self.df_source['Time'].iloc[0] = 0
        
    def phenomena_analysis(self, bxdata_path):
        """Проверка наличия условий для дефлаграции и детонации"""
        """перечень колонок DataFrame, где содержится признак 0/1/3 по конкретному боксу"""
        columns_by_box = self.df_source.columns[1:-2].tolist()
        
        for phenomenon in self.phenomena_for_analysis:
            self.myInfo.send('analyzing of conditions for {} is started'.format(phenomenon))
            if check_conditions_for(phenomenon, self.df_source):
                self.existing_phenomena.append(phenomenon)
                self.myInfo.send('----> {} is there'.format(phenomenon))
                """создание колонки с номерами боксов с условиями для горения/детонации"""
                self.df_source[(phenomenon,'boxes')] =  list(map(lambda i: get_boxes_number_by_phenomenon(self.df_source.loc[i][columns_by_box], phenomenon), self.df_source.index.tolist()))
                self.myInfo.send('----> boxes with {} are collected'.format(phenomenon))
                """суммарный объем боксов с условиями для горения/детонации"""
                self.df_source[(phenomenon,'volume')] = self.df_source[(phenomenon,'boxes')].apply(lambda list_boxes: sum_volumes_by_number(list_boxes, bxdata_path))
                self.myInfo.send('----> boxes volume with {} are calculated'.format(phenomenon))
            else:
                self.myInfo.send('----> there is no {}'.format(phenomenon))
        
        """удаляем ненужные (теперь) колонки, вводим multiindexes"""
        self.df_source = self.df_source.drop(columns=columns_by_box)
        self.df_source = self.df_source.rename(columns={"Time": ("Time", 'begin')})
        
        """ добавляем конец интервала """
        index_list = [i+1 for i in self.df_source.index.tolist()]
        self.df_source[("Time", 'end')] = list(map(lambda i: self._get_time_or_end_calc(self.df_source[('Time','begin')], i), index_list))
        
        self.df_source.columns= pd.MultiIndex.from_tuples(self.df_source.columns)
        self.df_source = self.df_source[["Time", 'deflagration', 'detonation']]
        
    def create_second_dataframe(self, config, phenomenon):
        """собираем новый датафрейм. Теперь анализ пойдет по помещениям внутри каждого временного слоя.
        необходимs только два столбца по каждоиму феномену, объемы легче пересобрать для новых групп агрегирующей функцией,
        чем тянуть за собой"""
        self.df = pd.DataFrame({'Time': self.df_source[self.df_source[(phenomenon,'is')]==True][('Time','begin')],
                           'Boxes': self.df_source[self.df_source[(phenomenon, 'is')]==True][(phenomenon,'boxes')]})
         
        """Данные по помещениям, группировка по помещениям"""
        """словарь соответствия боксов и помещений из конфиг-файла"""
        rooms_dict = {room: config.getlist('rooms', room) for room in config['rooms']}
        
        self.df['rooms_boxes'] = list(map(lambda box: get_rooms(rooms_dict, box), self.df['Boxes']))
        self.df['rooms'] = [list(self.df.loc[i]['rooms_boxes'].keys()) for i in self.df.index.tolist()]
        self.df['Boxes'] = [list(self.df.loc[i]['rooms_boxes'].values()) for i in self.df.index.tolist()]
        
        self.df = self.df.drop(columns='rooms_boxes')
        
    def index_by_time(self):
        """ на новый слой переходим при изменении помещения и, если процесс (горение/детонация) временно прекращается;
        поскольку в self.df попадают только строки с моментами времени, когда феномен наблюдается, прекращение процесса
        фиксируем по изменению индекса"""
       
        """шаг изменения индексов"""
        dif_index = [self.df.index[i] - self.df.index[i-1] for i in range(1,len(self.df.index))] 
        dif_index.insert(0,1) # добавляем единицу в начало списка

        """создание экземпляра класса, инициация первым элементом"""
        time_index = TimeIndex(self.df['rooms'].tolist()[0])
    
        """генерация индекса в зависимости от помещения и изменения индекса строки """
        self.df['time_index'] = [time_index.get(self.df['rooms'].tolist()[i], dif_index[i]) for i in range(len(self.df['rooms'].tolist()))]

    
    def split_by_rooms_layers(self):
        """Добавление слоев по помещениям"""
        buf = [split_row_by_rooms(self.df.loc[i],"Boxes","rooms") for i in self.df.index.tolist()]
        """пересобираем DataFrame"""
        self.df = pd.DataFrame([i for j in buf for i in j])
        
    def groupby(self, columns_names, agg_func_selection): #list, dict
        self.df = self.df.groupby(["time_index","rooms"]).agg(agg_func_selection)
        
    def add_times_data(self):   
        times_values = self.df_source.loc[:,('Time','begin')]
        index_list = [i for i in self.df.loc[:]['Time']['idxmin'].tolist()]
        self.df[('Time_interval','begin')] =  list(map(lambda i: self._get_time_or_end_calc(times_values, i), index_list))
    
        index_list = [i+1 for i in self.df.loc[:]['Time']['idxmax'].tolist()]
        self.df[('Time_interval','end')] = list(map(lambda i: self._get_time_or_end_calc(times_values, i), index_list)) 
        
    def add_concentration_data(self, conc_dict): #dict{pandas.DataFrame}
        """ храним значения всех концентраций водорода {индекса строки, индекса столбца (номер бокса): концентрация"""
        row_index_list = [range(self.df.loc[i]['Time']['idxmin'], self.df.loc[i]['Time']['idxmax']+1) for i in self.df.index.tolist()]
        col_index_list = self.df['Boxes']['boxes_numbers'].tolist()
        self.df[('Concentration','C_H2')] = [{(r,c): conc_dict["C_H2"].iloc[r][c] for r in row_index_list[i] for c in col_index_list[i]} for i in range(len(self.df.index.tolist()))]
    
        """ храним (индекс строки, индекса столбца (номер бокса)) максимального значения концентрации""" 
        self.df[('Concentration','C_H2')] = self.df[('Concentration','C_H2')].apply(lambda d: max(d, key=d.get))
        
        """ записываем концентрации кислорода и пара для индексов строки и столбца, соответствующих максимальной концентрации водорода""" 
        self.df[('Concentration','C_O2')] = [conc_dict["C_O2"].iloc[r_c] for r_c in self.df[('Concentration','C_H2')]]
        self.df[('Concentration','C_v')] = [conc_dict["C_v"].iloc[r_c] for r_c in self.df[('Concentration','C_H2')]]
        
        # записываем момент времени по индексу строки, соответствующий максимальной концентрации водорода 
        self.df[('Concentration','time')] = [conc_dict["C_H2"].loc[r_c[0]]['Time'] for r_c in self.df[('Concentration','C_H2')]]
        # записываем бокс по индексу столбцаи, соответствующего максимальной концентрации водорода 
        self.df[('Concentration','box')] = ['Box_{}'.format(r_c[1]) for r_c in self.df[('Concentration','C_H2')]]
        # финально переписываем максимальную концентрацию водорода по индексам строки и столбца, соответствующих их максимальному значению 
        self.df[('Concentration','C_H2')] = [conc_dict["C_H2"].iloc[r_c] for r_c in self.df[('Concentration','C_H2')]]
        