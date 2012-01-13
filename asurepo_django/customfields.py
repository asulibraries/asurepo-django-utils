import json

import django.db.models as models

class JsonField(models.TextField):

    __metaclass__ = models.SubfieldBase
    
    def __init__(self, *args, **kwargs):
        
        # set encoder from input or default
        if 'encoder' in kwargs:
            self.encoder = kwargs.get('encoder')
            del kwargs['encoder']
        else:
            self.encoder = json.JSONEncoder()
        
        # set decoder from input or default
        if 'decoder' in kwargs:
            self.decoder = kwargs.get('decoder')
            del kwargs['decoder']
        else:
            self.decoder = json.JSONDecoder()

        super(JsonField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        
        if value == '':
            return None

        try:
            if isinstance(value, basestring):
                return self.decoder.decode(value)
        except ValueError:
            pass

        return value

    def get_db_prep_value(self, value, connection, prepared):
        if value == '':
            return None

        if isinstance(value, dict) or isinstance(value, list):
            return self.encoder.encode(value)

        return value

class ChoiceEnumField(models.IntegerField):

    __metaclass__ = models.SubfieldBase

    def __init__(self, *args, **kwargs):
        # assert that 'choices' argument is a ChoiceEnum object
        self.enum = kwargs.get('choices', lambda x: x)
        super(ChoiceEnumField, self).__init__(*args, **kwargs)

    def get_db_prep_value(self, value, connection, prepared):
        return int(self.enum(value))

    def to_python(self, value):
        return self.enum(value)

from south.modelsinspector import add_introspection_rules
add_introspection_rules([], ["^asurepo\.django\.customfields\.JsonField"])
add_introspection_rules([], ["^asurepo\.django\.customfields\.ChoiceEnumField"])
