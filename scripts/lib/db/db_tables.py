#!/usr/bin/env python3
"""
Uses 'sqlalchemy' library to create a simple 'sqlite' db to hold query results for models
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from sqlalchemy.schema import ForeignKey, PrimaryKeyConstraint
from sqlalchemy.exc import DatabaseError

QUERY_DB_FILE = 'query_data.db'

Base = declarative_base()

# pylint: disable=R0903
class Query(Base):
    ''' **Query table**

        Basic idea is to have a "query" table that points to the various parts of the model.
        A website query will provide the name of the model and a label from within the model.
        This can be used as an index to a row of the table.

        The "query" table points to the "info" tables. These point to information at various
        levels of the model:
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

    segment_info = relationship('SegmentInfo')
    part_info = relationship('PartInfo')
    model_info = relationship('ModelInfo')
    user_info = relationship('UserInfo')

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


class SegmentInfo(Base):
    ''' **Segment_Info table**

        Any information derived from a segment within a 3d model part,
        e.g. a single triangle on a fault surface made of lots of triangles
    '''
    __tablename__ = "segment_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    json = Column(String, unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)



class PartInfo(Base):
    ''' **Part_Info table**

        Any information derived from a model part
        e.g. fault surface, borehole
    '''
    __tablename__ = "part_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    json = Column(String, unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)


class ModelInfo(Base):
    ''' **Model_Info table**

        Any information that comes from the model as a whole,
        e.g. CRS of the model
    '''
    __tablename__ = "model_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    json = Column(String, unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)


class UserInfo(Base):
    ''' **User_Info table**

        Any user notes that must be kept separate from the model data update process
        e.g. links to external databases
    '''
    __tablename__ = "user_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    json = Column(String, unique=True)

    def __repr__(self):
        return "{1}: json={0}\n".format(self.json, self.__class__.__name__)


class KeyValuePairs(Base):
    ''' **KeyValuePairs table**

        Stores key value pairs
    '''
    __tablename__ = "keyvaluepairs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String)
    value = Column(String, nullable=False)
    is_url = Column(Boolean)

#
class QueryDB():
    ''' A simple database class to manage the creation, writing and reading of the query database
    '''
    def __init__(self, create=False, db_name='query_data.db'):
        self.error = ''
        try:
            db_name = 'sqlite:///' + db_name
            eng = create_engine(db_name, echo=False)
            Base.metadata.bind = eng
            if create:
                Base.metadata.drop_all()
                Base.metadata.create_all()
            # 'scoped_session()' makes a thread-safe cache of session objects
            #  NOTE: Would like to ventually make scope_session() more global
            self.session_obj = scoped_session(sessionmaker(eng))
            self.ses = self.session_obj()
        except DatabaseError as db_exc:
            self.error = str(db_exc)

    def get_error(self):
        """
        :returns: the current error message
        """
        return self.error

    def add_segment(self, json_str):
        """
        Adds a segment object to database

        :param json_str: segment object as a JSON string
        :returns: a tuple (True, seginfo_obj) if successful
                          (False, exception string) if operation failed
        """
        try:
            seginfo_obj = self.ses.query(SegmentInfo).filter_by(json=json_str).first()
            if seginfo_obj is None:
                seginfo_obj = SegmentInfo(json=json_str)
                self.ses.add(seginfo_obj)
                self.ses.commit()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        return True, seginfo_obj

    def add_part(self, json_str):
        """
        Adds a part object to database

        :param json_str: part object as a JSON string
        :returns: a tuple (True, partinfo_obj) if successful
                          (False, exception string) if operation failed
        """
        try:
            part_obj = self.ses.query(PartInfo).filter_by(json=json_str).first()
            if part_obj is None:
                part_obj = PartInfo(json=json_str)
                self.ses.add(part_obj)
                self.ses.commit()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        return True, part_obj

    def add_model(self, json_str):
        """
        Adds a model object to database

        :param json_str: model object as a JSON string
        :returns: a tuple (True, model_obj) if successful
                          (False, exception string) if operation failed
        """
        try:
            model_obj = self.ses.query(ModelInfo).filter_by(json=json_str).first()
            if model_obj is None:
                model_obj = ModelInfo(json=json_str)
                self.ses.add(model_obj)
                self.ses.commit()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        return True, model_obj

    def add_user(self, json_str):
        """
        Adds a user info object to database

        :param json_str: user info object as a JSON string
        :returns: a tuple (True, userinfo_obj) if successful
                          (False, exception string) if operation failed
        """
        try:
            userinfo_obj = self.ses.query(UserInfo).filter_by(json=json_str).first()
            if userinfo_obj is None:
                userinfo_obj = UserInfo(json=json_str)
                self.ses.add(userinfo_obj)
                self.ses.commit()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        return True, userinfo_obj

    def add_query(self, label, model_name, segment, part, model, user):
        """
        Adds a query object to database

        :param json_str: query object as a JSON string
        :returns: a tuple (True, query_obj) if successful
                          (False, exception string) if operation failed
        """
        try:
            query_obj = Query(label=label, model_name=model_name, segment_info=segment,
                              part_info=part, model_info=model, user_info=user)
            self.ses.merge(query_obj)
            self.ses.commit()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        return True, None

    def query(self, label, model_name):
        """
        Use this to query the database

        :param label: model part label
        :param model_name: name of model
        :returns: a tuple, format is (True, label str, model_name, seg_info_dict, part_info_dict,
                      model_info_dict, user_info_dict) if successful
                else (False, exception string)
        """
        try:
            result = self.ses.query(Query).filter_by(label=label) \
                                          .filter_by(model_name=model_name).first()
        except DatabaseError as db_exc:
            return False, str(db_exc)
        if result is None:
            filter_str = label.rpartition('_')[0]
            try:
                result = self.ses.query(Query).filter_by(model_name=model_name) \
                                              .filter_by(label=filter_str).first()
            except DatabaseError as db_exc:
                return False, str(db_exc)
        if result is None:
            return True, (None, None, None, None, None, None)
        return True, (result.label, result.model_name, getattr(result.segment_info, 'json', None),
                      getattr(result.part_info, 'json', None),
                      getattr(result.model_info, 'json', None),
                      getattr(result.user_info, 'json', None))

    def __del__(self):
        try:
            self.session_obj.remove()
        except DatabaseError:
            pass



if __name__ == "__main__":
    print("Testing query db")
    # Basic unit testing
    QUERY_DB = QueryDB(create=True, db_name=':memory:')
    MSG = QUERY_DB.get_error()
    if MSG != '':
        print(MSG)
    assert MSG == ''
    OK, S = QUERY_DB.add_segment('seg')
    assert OK
    OK, S2 = QUERY_DB.add_segment('seg')
    assert OK

    # Test for no duplicates
    Q = QUERY_DB.ses.query(SegmentInfo)
    assert Q.count() == 1

    OK, S3 = QUERY_DB.add_segment('seg3')
    assert OK
    OK, P = QUERY_DB.add_part('part')
    assert OK
    OK, M = QUERY_DB.add_model('model')
    assert OK
    OK, U = QUERY_DB.add_user('user')
    assert OK
    OK, MSG = QUERY_DB.add_query('label', 'model_name', S, P, M, U)
    assert OK
    OK, MSG = QUERY_DB.add_query('label2', 'model_name2', S3, P, M, U)
    assert OK
    OK, MSG = QUERY_DB.add_query('label_3_i', 'model_name3', S3, P, None, None)
    assert OK

    # Have added three 'Query' objs? two 'Segment_Info' objs ? etc.
    assert QUERY_DB.ses.query(Query).count() == 3
    assert QUERY_DB.ses.query(SegmentInfo).count() == 2
    assert QUERY_DB.ses.query(PartInfo).count() == 1
    assert QUERY_DB.ses.query(ModelInfo).count() == 1
    assert QUERY_DB.ses.query(UserInfo).count() == 1

    # LoOK for a 'Query' with all info tables
    OK, Q1 = QUERY_DB.query('label2', 'model_name2')
    assert(OK and Q1 is not None and Q1[0] == 'label2' and Q1[1] == 'model_name2' \
           and Q1[2] == 'seg3')

    # LoOK for 'Query' containing Nones
    OK, Q2 = QUERY_DB.query('label_3_i', 'model_name3')
    assert(OK and Q2[0] == 'label_3_i' and Q2[1] == 'model_name3' and Q2[5] is None)

    # LoOK for 'Query' with trailling number in label
    OK, Q2 = QUERY_DB.query('label_3_i_44', 'model_name3')
    assert(OK and Q2[0] == 'label_3_i' and Q2[1] == 'model_name3' and Q2[5] is None)

    # Non existing 'Query'
    assert QUERY_DB.query('label1_6', 'model_name5') == (True, (None, None, None, None, None, None))
    assert QUERY_DB.query('_label6', 'model_name5') == (True, (None, None, None, None, None, None))

    print("PASSED QUERY DB TESTS")
