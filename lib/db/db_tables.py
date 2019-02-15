#!/usr/bin/env python3

import sys

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.schema import ForeignKey, UniqueConstraint, PrimaryKeyConstraint
from sqlalchemy.exc import IntegrityError, DatabaseError

Base = declarative_base()


class Query(Base):
    ''' Basic idea is to have a "query" table that points to the various parts of the model.
        A website query will provide the name of the model and a label from within the model.
        This can be used as an index to a row of the table.
 
        The "query" table points to the "info" tables. These point to information at various levels of the model:
            segments, parts, model, and independent user notes.

        At the moment only a simple json string is stored in each of the "info" tables. 
    '''
    __tablename__ = "query"

    model_name = Column(String)
    label = Column(String)
    segment_info_id = Column(Integer, ForeignKey("segment_info.id"))
    part_info_id = Column(Integer, ForeignKey("part_info.id"))
    model_info_id = Column(Integer, ForeignKey("model_info.id"))
    user_info_id = Column(Integer, ForeignKey("user_info.id"))

    segment_info = relationship('Segment_Info')
    part_info = relationship('Part_Info')
    model_info = relationship('Model_Info')
    user_info = relationship('User_Info')

    __table_args__ = (PrimaryKeyConstraint('model_name', 'label', name='_query_uc'),)

    def __repr__(self):
        result = "Query:" + \
                 "\n    model_name={0}".format(self.model_name) + \
                 "\n    label={0}".format(self.label) + \
                 "\n    segment_info={0}".format(self.segment_info) + \
                 "\n    part_info={0}".format(self.part_info) + \
                 "\n    model_info={0}".format(self.model_info) + \
                 "\n    user_info={0}".format(self.user_info)
        return result


class Segment_Info(Base):
    ''' Any information derived from a segment within a 3d model part,
        e.g. a single triangle on a fault surface made of lots of triangles
    '''
    __tablename__ = "segment_info"
   
    id = Column(Integer, primary_key=True, autoincrement=True)
    json = Column(String, unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)



class Part_Info(Base):
    ''' Any information derived from a model part
        e.g. fault surface, borehole
    '''
    __tablename__ = "part_info"
   
    id = Column(Integer, primary_key=True, autoincrement=True)
    json = Column(String, unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)


class Model_Info(Base):
    ''' Any information that comes from the model as a whole, 
        e.g. CRS of the model
    '''
    __tablename__ = "model_info"
   
    id = Column(Integer, primary_key=True, autoincrement=True)
    json = Column(String, unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)


class User_Info(Base):
    ''' Any user notes that must be kept separate from the model data update process
        e.g. links to external databases
    '''
    __tablename__ = "user_info"
   
    id = Column(Integer, primary_key=True, autoincrement=True)
    json = Column(String, unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)
    
    
class KeyValuePairs(Base):
    __tablename__ = "keyvaluepairs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String)
    value = Column(String, nullable=False)
    is_url = Column(Boolean)
    
#
class QueryDB():
    ''' A simple database class to manage the creation, writing and reading of the query database
    '''
    def __init__(self):
        self.eng = None
        self.ses = None

    def open_db(self, create=False, db_name='query_data.db'):
        try:
            db_name = 'sqlite:///' + db_name
            self.eng = create_engine(db_name)
            Base.metadata.bind = self.eng
            if create:
                Base.metadata.drop_all()        
                Base.metadata.create_all()        
            Session = sessionmaker(bind=self.eng)
            self.ses = Session()
        except DatabaseError as e:
            return False, str(e)
        return True, None
            
        

    def add_segment(self, json_str):
        try:
            s = self.ses.query(Segment_Info).filter_by(json=json_str).first()
            if s == None:
                s = Segment_Info(json=json_str)
                self.ses.add(s)
                self.ses.commit()
        except DatabaseError as e:
            return False, str(e)
        return True, s
        
    def add_part(self, json_str):
        try:
            p = self.ses.query(Part_Info).filter_by(json=json_str).first()
            if p == None:
                p = Part_Info(json=json_str)
                self.ses.add(p)
                self.ses.commit()
        except DatabaseError as e:
            return False, str(e)
        return True, p

    def add_model(self, json_str):
        try:
            m = self.ses.query(Model_Info).filter_by(json=json_str).first()
            if m == None:
                m = Model_Info(json=json_str)
                self.ses.add(m)
                self.ses.commit()
        except DatabaseError as e:
            return False, str(e)   
        return True, m

    def add_user(self, json_str):
        try:
            u = self.ses.query(User_Info).filter_by(json=json_str).first()
            if u == None:
                u = User_Info(json=json_str)
                self.ses.add(u)
                self.ses.commit()
        except DatabaseError as e:
            return False, str(e)       
        return True, u

    def add_query(self, label, model_name, segment, part, model, user):
        try:
            q = Query(label=label, model_name=model_name, segment_info=segment, part_info=part, model_info=model, user_info=user)
            self.ses.merge(q)
            self.ses.commit()
        except DatabaseError as e:
            return False, str(e)
        return True, None

    def query(self, label, model_name):
        try:
            result = self.ses.query(Query).filter_by(label=label).filter_by(model_name=model_name).first()
        except DatabaseError as e:
            return False, str(e)
        if result == None:
            filter = label.rpartition('_')[0]
            try:
                result = self.ses.query(Query).filter_by(label=filter).first()
            except DatabaseError as e:
                return False, str(e)
        if result == None:
            return True, (None, None, None, None, None, None)
        return True, (result.label, result.model_name, getattr(result.segment_info, 'json', None), getattr(result.part_info, 'json', None), getattr(result.model_info, 'json', None), getattr(result.user_info, 'json', None))
        


if __name__ == "__main__":
    # Basic unit testing
    qd = QueryDB()
    ok, msg = qd.open_db(create=True, db_name=':memory:')
    if not ok:
        print(msg)
    assert(ok)
    ok, s = qd.add_segment('seg')
    assert(ok)
    ok, s2 = qd.add_segment('seg')
    assert(ok)

    # Test for no duplicates
    q = qd.ses.query(Segment_Info)
    assert(q.count()==1)

    ok, s3 = qd.add_segment('seg3')
    assert(ok)
    ok, p = qd.add_part('part')
    assert(ok)
    ok, m = qd.add_model('model')
    assert(ok)
    ok, u = qd.add_user('user')
    assert(ok)
    ok, msg = qd.add_query('label', 'model_name', s, p, m, u)
    assert(ok)
    ok, msg = qd.add_query('label2', 'model_name2', s3, p, m, u)
    assert(ok)
    ok, msg = qd.add_query('label_3_i', 'model_name3', s3, p, None, None)
    assert(ok)

    # Have added three 'Query' objs? two 'Segment_Info' objs ? etc.
    assert(qd.ses.query(Query).count()==3)
    assert(qd.ses.query(Segment_Info).count()==2)
    assert(qd.ses.query(Part_Info).count()==1)
    assert(qd.ses.query(Model_Info).count()==1)
    assert(qd.ses.query(User_Info).count()==1)

    # Look for a 'Query' with all info tables
    ok, q1 = qd.query('label2', 'model_name2')
    assert(ok and q1 != None and q1[0] == 'label2' and q1[1] == 'model_name2' and q1[2] == 'seg3')

    # Look for 'Query' containing Nones
    ok, q2 = qd.query('label_3_i', 'model_name3')
    assert(ok and q2[0] == 'label_3_i' and q2[1] == 'model_name3' and q2[5] == None)

    # Look for 'Query' with trailling number in label
    ok, q2 = qd.query('label_3_i_44', 'model_name3')
    assert(ok and q2[0] == 'label_3_i' and q2[1] == 'model_name3' and q2[5] == None)

    # Non existing 'Query'
    assert(qd.query('label1_6', 'model_name5') == (True, (None, None, None, None, None, None)))
    assert(qd.query('_label6', 'model_name5') == (True, (None, None, None, None, None, None)))

    print("PASSED TESTS")

    
