from abc import ABC, abstractmethod
import numpy as np
import matplotlib.pyplot as plt

from utils import nearest, round_sig, check_conditions_for

"""Отрисовка диаграмм реализовано на классах"""

class PlotDetonationBase(ABC):
    """абстрактный класс, хранит атрибуты и методы, используемые всеми модулями для отрисовки диаграмм"""
    def __init__(self, config):
        self.name = self.get_plot_name(config)
        self.figsize = tuple([float(a) for a in config["picture"]["picture_size"].split(", ")])
        self.bars_begin_times = {'deflagration': [], 'detonation': []}
        self.bars_height = {'deflagration': [], 'detonation': []}
        self.bars_wide = {'deflagration': [], 'detonation': []}
        self.xlim = None
        self.df = None # dataframe для отрисовки
            
    @staticmethod
    def get_plot_name(config):
        name = config["general"]["INPUT_DIR_PATH"].split('\\')[-1]
        name = name.replace('.','_')
        return 'res__' + name
        
    def _set_xaxis_arrays(self, phenomena):
        """ввод новых переменных для улучшения читаемости кода"""
        begin_times = {}
        end_times = {}
        for phenomenon in phenomena:
            begin_times[phenomenon] = self.df.loc[self.df[(phenomenon,'is')]==True][('Time', 'begin')].tolist()
            end_times[phenomenon] = self.df[self.df[(phenomenon,'is')]==True][('Time', 'end')].tolist()
        
            """поскольку бар на диаграмме рисуется вокруг значения X (пол ширины бара слева, пол ширины - справа) для корретного отображения начала и конца диапазона горения
            координаты Х нужно смещать на пол ширины влево"""
            self.bars_wide[phenomenon] = list(map(lambda x,y: y-x, begin_times[phenomenon], end_times[phenomenon]))
            self.bars_begin_times[phenomenon] = list(map(lambda x,y: (x+y/2), begin_times[phenomenon], self.bars_wide[phenomenon]))
        
        self.xlim = (0, self.df[('Time','end')].tolist()[-1]) # базово ось Х идет от 0 до конца расчета

    def _set_left_yaxis_array(self):
        pass
    
    def plot(self, df_source):    
        """ если детонация/дефлограция начинается на последнем шаге, то построить бар будет невозможно -
        работаем с DataFrame без последнего шага"""
        self.df = df_source.iloc[:-1, :]
        
        fig = plt.figure(figsize=self.figsize)
        ax = fig.add_axes(self.rect)
        return ax
    
class PlotDetonationOne(PlotDetonationBase):
    def __init__(self, config):
        super().__init__(config)
    
        self.rect =[0.08,0.15,0.88,0.80] #?
        self.major_yticks = [0.8,1.75]
        self.ylabels_my = ['COMBUSTION','DETONATION']
        
    def _set_xaxis_arrays(self, phenomena):
        super()._set_xaxis_arrays(phenomena)
        """для случая без горения и детонации"""
        if self.bars_begin_times['deflagration'] != []:
            self.xlim = (self.bars_begin_times['deflagration'][0]*0.98, self.bars_begin_times['deflagration'][-1])
    
    def _set_left_yaxis_array(self): 
        self.bars_height['deflagration'] = [self.major_yticks[0] for k  in self.bars_begin_times['deflagration']]
        self.bars_height['detonation'] = [self.major_yticks[1] for k in self.bars_begin_times['detonation']]
        
    def plot(self, solve):
        ax = super().plot(solve.df_source)
        
        self._set_xaxis_arrays(solve.existing_phenomena)
        solve.myInfo.send('----> X-Axis arrays is completed')
        self._set_left_yaxis_array()
        solve.myInfo.send('----> Y-Axis arrays is completed')
       
        plt.bar(self.bars_begin_times['deflagration'],  self.bars_height['deflagration'], width = self.bars_wide['deflagration'], color = 'blue', edgecolor = 'blue')
        if check_conditions_for('detonation', self.df):
            plt.bar(self.bars_begin_times['detonation'],  self.bars_height['detonation'], width = self.bars_wide['detonation'], color = 'orange', edgecolor = 'orange')
        
        ax.set_yticks(self.major_yticks)
        ax.set_yticklabels(self.ylabels_my, rotation=90, verticalalignment='top')
        
        """Настройки оси X"""
        ax.set_xlim(self.xlim)
        ax.set_xlabel('Time, s')
        ax.grid(visible=True, which='major', axis='both', color='black', linestyle='--', linewidth = 1)
        
        plt.savefig('{}\\{}\\{}'.format(solve.solve_path, "results", self.name))
        plt.show()

class PlotDetonationTwo(PlotDetonationBase):
    def __init__(self, config):
        super().__init__(config)
          
        self.rect =[0.08,0.15,0.83,0.80]
        self.max_volume_with_name = {}#{'deflagration': [], 'detonation': []}

    def _set_yaxis_array_with_name(self, name):
        self.max_volume_with_name[name] = self.df[(name,'volume')].max()
        self.bars_height[name] = [v/self.max_volume_with_name[name] for v in self.df[self.df[(name,'is')]==True][(name,'volume')].to_list()]
           
    def _plot_combustion(self, ax):
        ax.set_ylabel('COMBUSTION')
        ax.bar(self.bars_begin_times['deflagration'],  self.bars_height['deflagration'], width = self.bars_wide['deflagration'], color = 'blue', edgecolor = 'blue')
     
    def _plot_detonation(self, ax1):
        ax1.set_ylabel('DETONATION',color='k')
        ax1.bar(self.bars_begin_times['detonation'],  self.bars_height['detonation'], width = self.bars_wide['detonation'], color = 'orange', edgecolor = 'orange')
        
        """ необходимо, чтобы на правой оси было бы столько же делений
        и деления были строго напротив делений на левой оси, чтобы сеточные линии были едины
        установка y ticks: 5 шагов, шаг округлен по значащим цифрам до ...Х0 или ...Х5"""
        ax1_step = self.max_volume_with_name['detonation']/self.max_volume_with_name['deflagration']/5
        ax1_step = nearest((round_sig(ax1_step), round_sig(2*ax1_step)/2), ax1_step)
        ax1_yticks = np.arange(0, ax1_step*6, ax1_step)
        ax1.set_yticks(ax1_yticks)
        
        """ максимум левой оси выше последнего деления в 1.05
         устанавливаем аналогично максимум правой """
        ax1_max = ax1.get_yticks()[-1]
        ax1.set_ylim(ymax = ax1_max*1.05, ymin=0)
    
    def plot(self, solve):    
        ax = super().plot(solve.df_source)

        self._set_xaxis_arrays(solve.existing_phenomena)
        solve.myInfo.send('----> X-Axis arrays is completed')
        self._set_yaxis_array_with_name('deflagration')
        solve.myInfo.send('----> Left Y-Axises arrays is completed')
        self._plot_combustion(ax)
        
        if check_conditions_for('detonation', self.df):
            self._set_yaxis_array_with_name('detonation')
            solve.myInfo.send('----> Right Y-Axises arrays is completed')
            ax1 = ax.twinx()
            self._plot_detonation(ax1)
        
        """Настройки оси X"""
        ax.set_xlim(self.xlim)
        ax.set_xlabel('Time, s')
        
        """Надпись со значение максимального объема помещений, в котором возможно горение"""
        ax.text(ax.get_xlim()[0],-0.15,'Max. ignitable mixture volume, m^3: {}'.format(round(self.max_volume_with_name['deflagration'],1)) ,fontsize = 9, color='k')
        
        """ Линии сетки"""
        ax.yaxis.grid(True, which=u'major',linewidth = 0.5, color='k')#, linestyle='-',)
        ax.xaxis.grid(True, which=u'major',linewidth = 0.5, color='k')
        
        plt.savefig('{}\\{}\\{}'.format(solve.solve_path, "results", self.name))
        plt.show()
