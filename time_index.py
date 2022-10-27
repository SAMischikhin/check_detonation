
class TimeIndex():
    def __init__(self, init_value):
        self.init_value = init_value
        self.g = self.generator()
        self.g.send(None) #запуск генератора

    @staticmethod
    def generator():
        i=0
        while 1:
            b = yield i
            if b == False:
                i+=1
    
    def get(self,value, value2):
        """ помнит прошлое значение, выдает его или следующий индекс"""
        """ условия, при которых индекс не меняется """
        condition1 = bool(value == self.init_value)
        condition2 = bool(value2 == 1)
        res = self.g.send(condition1 and condition2)
        self.init_value = value
        return res