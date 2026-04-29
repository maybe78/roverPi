import re
import json

log_message = '''"message": "[Получение списка замечаний, включенных в ЛУЗ, из списка ревизий] Ответ от редактора: HttpResponseImpl[request=HttpRequestImpl[method=POST, url=http://pp2.aissd.mos.ru/de-npa/api/v1/npa/document/formalRemarks, headers={Content-Length=[327], Content-Type=[application/json], Cookie=[JWT-AUTH-TOKEN=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.sdHBO8QzhQ1wMJ8ZHaTYNt7KuX22_9e7VFiV47ZllW8], X-NPA-Request-id=[dbade9ea-59a7-4a66-98ca-6e12b102cac0]}, protocolVersion=HTTP/1.1], httpMeta=HttpMetaImpl[statusCode=200, headers={cache-control=[no-store], connection=[keep-alive], content-length=[724], content-type=[application/json], date=[Fri, 21 Nov 2025 10:32:15 GMT]}], body=FormalRemarksLdeResponse(documents=[FormalRemarksLdeResponse.DocumentRevisionRemarks(documentId=0aec53e1-55e9-4775-9e97-6a47aeb10211, revisionId=7d11c25b-f088-4400-9aef-54d6adebd373, remarks=[FormalRemarksLdeResponse.Remark(id=bc407323-2399-4d74-b12f-524987e06e2c, position=1), FormalRemarksLdeResponse.Remark(id=6b58c5af-0e8d-4476-b91c-5b08496a0331, position=2)]), FormalRemarksLdeResponse.DocumentRevisionRemarks(documentId=b2325c73-e6cb-4e6d-a757-103fc920344d, revisionId=b3c7e113-fd81-4f20-bbbf-746190880862, remarks=[FormalRemarksLdeResponse.Remark(id=6e9ccc1c-3b3e-4564-b8c8-61a189e0b4f7, position=1), FormalRemarksLdeResponse.Remark(id=259ad7ca-e822-4492-8de0-57b2d289e189, position=2)]), FormalRemarksLdeResponse.DocumentRevisionRemarks(documentId=f009cb48-9e17-4574-bd6c-ce558f54d63e, revisionId=330a1b6d-c1a4-4b21-9d78-010e8acc6910, remarks=[FormalRemarksLdeResponse.Remark(id=239d98c0-9d58-40ad-8ea7-285e7d030f90, position=1), FormalRemarksLdeResponse.Remark(id=65279494-d205-446f-a869-fc0eb88d4fc2, position=2)])])]",'''

class JavaToStringParser:
    def __init__(self, text):
        # Находим начало основного объекта (например, HttpResponseImpl[...)
        # Пропускаем текстовый префикс "[INFO] ..."
        match = re.search(r':\s*(\w+(?:Impl|Response)?\[)', text)
        if match:
            self.text = text[match.start(1):]
        else:
            self.text = text
        self.pos = 0
        self.length = len(self.text)

    def parse(self):
        return self.parse_value()

    def peek(self):
        if self.pos < self.length:
            return self.text[self.pos]
        return None

    def consume(self):
        char = self.text[self.pos]
        self.pos += 1
        return char

    def parse_value(self):
        # Пропускаем пробелы
        while self.pos < self.length and self.text[self.pos].isspace():
            self.pos += 1
        
        if self.pos >= self.length:
            return None

        char = self.peek()

        # Если это список или карта
        if char == '[':
            return self.parse_list()
        elif char == '{':
            return self.parse_map()

        # Читаем значение или имя класса
        start = self.pos
        # Читаем пока не встретим разделитель (, ] ) } [)
        # Важно: '=' не является разделителем для значения (нужно для Cookie=...)
        while self.pos < self.length and self.text[self.pos] not in ',()[]{}\n':
            self.pos += 1
        
        value_str = self.text[start:self.pos].strip()

        # Проверяем, не является ли это классом перед объектом (ClassName[ или ClassName()
        if self.pos < self.length:
            next_char = self.text[self.pos]
            if next_char == '(':
                self.consume() # съедаем '('
                return self.parse_object(terminator=')', class_name=value_str)
            elif next_char == '[':
                self.consume() # съедаем '['
                return self.parse_object(terminator=']', class_name=value_str)

        return value_str

    def parse_object(self, terminator, class_name=None):
        obj = {}
        if class_name:
            obj['_type'] = class_name
        
        while self.pos < self.length:
            while self.pos < self.length and self.text[self.pos].isspace():
                self.pos += 1
            
            if self.peek() == terminator:
                self.consume()
                return obj

            # Читаем ключ
            key_start = self.pos
            while self.pos < self.length and self.text[self.pos] not in '=':
                self.pos += 1
            key = self.text[key_start:self.pos].strip()
            
            # Если есть '=', читаем значение
            if self.peek() == '=':
                self.consume()
                val = self.parse_value()
                obj[key] = val
            
            # Пропускаем запятую
            while self.pos < self.length and self.text[self.pos].isspace():
                self.pos += 1
            
            if self.peek() == ',':
                self.consume()
            elif self.peek() == terminator:
                continue
        return obj

    def parse_list(self):
        self.consume() # съедаем '['
        lst = []
        while self.pos < self.length:
            while self.pos < self.length and self.text[self.pos].isspace():
                self.pos += 1
            
            if self.peek() == ']':
                self.consume()
                return lst
            
            val = self.parse_value()
            lst.append(val)
            
            while self.pos < self.length and self.text[self.pos].isspace():
                self.pos += 1
            
            if self.peek() == ',':
                self.consume()
            elif self.peek() == ']':
                continue
        return lst

    def parse_map(self):
        self.consume() # съедаем '{'
        obj = {}
        while self.pos < self.length:
            while self.pos < self.length and self.text[self.pos].isspace():
                self.pos += 1
            
            if self.peek() == '}':
                self.consume()
                return obj
            
            # В map ключи отделены '=' от значений
            key_start = self.pos
            while self.pos < self.length and self.text[self.pos] not in '=':
                self.pos += 1
            key = self.text[key_start:self.pos].strip()
            
            if self.peek() == '=':
                self.consume()
                val = self.parse_value()
                obj[key] = val
            
            while self.pos < self.length and self.text[self.pos].isspace():
                self.pos += 1
            
            if self.peek() == ',':
                self.consume()
            elif self.peek() == '}':
                continue
        return obj

# Пример запуска
clean_log = log_message.strip().rstrip(',').rstrip("'").rstrip('"')
parser = JavaToStringParser(clean_log)
result = parser.parse()

# Вывод результата
print(json.dumps(result, indent=2, ensure_ascii=False))
