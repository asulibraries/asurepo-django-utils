import types

from peak.util import proxies

def ChoiceEnum(*choice_tuples):

    class ChoiceEnumList(proxies.ObjectWrapper):
        __choices_by_value = {}
        __choices_by_name = {}
        __choices_by_label = {}

        def __init__(self, *choice_tuples):
            django_choices = [(val, label) for val, _, label in choice_tuples]
            super(ChoiceEnumList, self).__init__(django_choices)

            for val, name, label in choice_tuples:
                wrapped_choice = ChoiceWrapper(val, name, label)
                self.__choices_by_value[val] = wrapped_choice
                self.__choices_by_name[self.__index_string(name)] = wrapped_choice
                self.__choices_by_label[self.__index_string(label)] = wrapped_choice

        def __index_string(self, string):
            return string.lower().replace('_', ' ')
            
        def __call__(self, value):
            '''Convert the input value to the appropriate ChoiceWrapper'''
            if type(value) is ChoiceWrapper:  
                # enable identity lookups
                return value
            if type(value) is types.IntType:
                return self.__choices_by_value[value]
            elif type(value) in types.StringTypes:
                # lookup by label, then name
                index_string = self.__index_string(value)
                choice = self.__choices_by_label.get(index_string)
                choice = choice or self.__choices_by_name.get(index_string)
                if choice is not None:
                    return choice
                else:  
                    # try casting to int as a last ditch effort - Django forms
                    # will 'clean' to unicode in some cases
                    try:
                        return self.__choices_by_value[int(value)]
                    except ValueError:
                        pass
            raise KeyError

        def labels(self):
            return [w.label for w in self]

        def __getattr__(self, attr):
            try:
                return self(attr)
            except KeyError:
                return super(ChoiceEnumList, self).__getattr__(attr)

    class ChoiceWrapper(proxies.ObjectWrapper):
        name = None
        label = None

        def __init__(self, value, name, label):
            super(ChoiceWrapper, self).__init__(value)
            self.name = name
            self.label = label

        def __call__(self):
            '''Make a call to this object return its 'primitive' value.'''
            return self
    
    return ChoiceEnumList(*choice_tuples)


