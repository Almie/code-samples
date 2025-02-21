from PySide2.QtCore import QThreadPool, QRunnable

class BaseAPIWrapper(object):
    def __init__(self):
        pass

    def connect(self):
        pass

def to_thread(func):
    def wrapper(*args, **kwargs):
        class RunnableFunc(QRunnable):
            def __init__(self, func, *args, **kwargs):
                QRunnable.__init__(self)
                self._func = func
                self._args = args
                self._kwargs = kwargs
            
            def run(self):
                self._func(*self._args, **self._kwargs)

        runnable = RunnableFunc(func, *args, **kwargs)
        QThreadPool.globalInstance().start(runnable)
    return wrapper
