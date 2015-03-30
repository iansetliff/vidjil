# coding: utf8
import gluon.contrib.simplejson, datetime
import vidjil_utils
if request.env.http_origin:
    response.headers['Access-Control-Allow-Origin'] = request.env.http_origin  
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Max-Age'] = 86400

ACCESS_DENIED = "access denied"

## return patient file list
##
def info():
    

    patient = db.patient[request.vars["id"]]

    if request.vars["config_id"] and request.vars["config_id"] != "-1" :
        config_id = long(request.vars["config_id"])
        patient_name = vidjil_utils.anon(patient.id, auth.user_id)
        config_name = db.config[request.vars["config_id"]].name

        fused = db(
            (db.fused_file.patient_id == patient)
            & (db.fused_file.config_id == config_id)
        )

        analysis = db(
            (db.analysis_file.patient_id == patient)
            & (db.analysis_file.config_id == config_id)
        )
        
        
        config = True
        fused_count = fused.count()
        fused_file = fused.select()
        fused_filename = patient_name +"_"+ config_name + ".data"
        analysis_count = analysis.count()
        analysis_file = analysis.select()
        analysis_filename = patient_name +"_"+ config_name + ".analysis"
        
    else:
        config_id = -1
        config = False
        fused_count = 0
        fused_file = ""
        fused_filename = ""
        analysis_count = 0
        analysis_file = ""
        analysis_filename = ""

    if config :

        query = db(
                (db.sequence_file.patient_id==db.patient.id)
                & (db.patient.id==request.vars["id"])
            ).select(
                left=db.results_file.on(
                    (db.results_file.sequence_file_id==db.sequence_file.id)
                    & (db.results_file.config_id==str(config_id) )
                ), 
                orderby = db.sequence_file.id|db.results_file.run_date,
                groupby = db.sequence_file.id,
            )

    else:

        query = db(
                (db.sequence_file.patient_id==db.patient.id)
                & (db.patient.id==request.vars["id"])
            ).select(
                left=db.results_file.on(
                    (db.results_file.sequence_file_id==db.sequence_file.id)
                    & (db.results_file.config_id==str(config_id) )
                )
            )


    
    log.debug('patient (%s)' % request.vars["id"])
    if (auth.has_permission('read', 'patient', request.vars["id"]) ):
        return dict(query=query,
                    patient=patient,
                    config_id=config_id,
                    fused_count=fused_count,
                    fused_file=fused_file,
                    fused_filename=fused_filename,
                    analysis_count=analysis_count,
                    analysis_file = analysis_file,
                    analysis_filename = analysis_filename,
                    config=config)
    
    
    else :
        res = {"message": ACCESS_DENIED}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))


def custom():
    if request.vars["config_id"] and request.vars["config_id"] != "-1" :
        config_id = long(request.vars["config_id"])
        config_name = db.config[request.vars["config_id"]].name
        config = True
        
    else:
        request.vars["config_id"] = -1
        config_id = -1
        config_name = None
        config = False
        
    if "custom_list" not in request.vars :
        request.vars["custom_list"] = []
    if type(request.vars["custom_list"]) is str :
        request.vars["custom_list"] = [request.vars["custom_list"]]
        

    q = ((auth.accessible_query('read', db.patient) | auth.accessible_query('admin', db.patient) ) 
                & (auth.accessible_query('read', db.config) | auth.accessible_query('admin', db.config) ) 
                & (db.sequence_file.patient_id==db.patient.id)
                & (db.results_file.sequence_file_id==db.sequence_file.id)
                & (db.results_file.scheduler_task_id==db.scheduler_task.id)
                & (db.scheduler_task.status=='COMPLETED')
                & (db.config.id==db.results_file.config_id)
            )

    query = db(q).select(
                orderby = ~db.sequence_file.patient_id|db.sequence_file.id|db.results_file.run_date,
                groupby = db.sequence_file.id|db.results_file.config_id,
            )

    ##filter
    if "filter" not in request.vars :
        request.vars["filter"] = ""
        
    for row in query :
        row.checked = False
        if (str(row.results_file.id) in request.vars["custom_list"]) :
            row.checked = True
        row.string = (vidjil_utils.anon(row.sequence_file.patient_id, auth.user_id) + row.sequence_file.filename +
                      str(row.sequence_file.sampling_date) + row.sequence_file.pcr + row.config.name + str(row.results_file.run_date)).lower()
    query = query.find(lambda row : ( vidjil_utils.filter(row.string,request.vars["filter"]) or row.checked) )
    
    if config :
        query = query.find(lambda row : ( row.results_file.config_id==config_id or (str(row.results_file.id) in request.vars["custom_list"])) )
    
    res = {"message": "custom list (%s)" % config_name}
    log.debug(res)

    return dict(query=query,
                config_id=config_id,
                config=config)
    

## return patient list
def index():
    if not auth.user : 
        res = {"redirect" : URL('default', 'user', args='login', scheme=True, host=True,
                            vars=dict(_next=URL('patient', 'index', scheme=True, host=True)))
            }
        
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))
    log.debug('patient list')

    count = db.sequence_file.id.count()
    isAdmin = auth.has_membership("admin")
    
    query_anon = query = db((db.auth_permission.name == "anon") & (db.auth_permission.table_name == "patient")).select(
        db.patient.ALL, db.auth_permission.ALL,
        left=[db.auth_permission.on(db.patient.id == db.auth_permission.record_id )])
    anon={}
    for row in query_anon:
        anon[row.patient.id] = row.auth_permission.name
    
    ##retrieve patient list 
    query = db(
        (auth.accessible_query('read', db.patient) | auth.accessible_query('admin', db.patient) ) &
        (auth.accessible_query('read', db.config) | auth.accessible_query('admin', db.config) ) &
        (db.auth_permission.name == "read") & (db.auth_permission.table_name == "patient")
    ).select(
        db.patient.ALL, db.fused_file.ALL, db.config.ALL, db.sequence_file.ALL, db.auth_permission.ALL,
        orderby = ~db.patient.id,
        left=[db.sequence_file.on(db.patient.id == db.sequence_file.patient_id), 
              db.fused_file.on( db.patient.id == db.fused_file.patient_id),
              db.config.on(db.fused_file.config_id == db.config.id),
              db.auth_permission.on(db.patient.id == db.auth_permission.record_id )]
    )

    result = []
    patient_id = 0
    sequence_file_id = 0
    
    for i, row in enumerate(query) :
        if row.patient.id != patient_id :
            patient_id = row.patient.id
            row2 = row
            row2.conf_list = []
            row2.conf_id_list = []
            row2.group_list = []
            row2.file_count = 0
            row2.size = 0
            result.append(row2)
                
        if row.sequence_file.id != sequence_file_id :
            row2.file_count += 1
            row2.size += row.sequence_file.size_file
            
        row2.conf_list.append(row.config.name)
        row2.conf_id_list.append(row.config.id)
        row2.group_list.append(str(row.auth_permission.group_id))
        

    for row in result :
        row.most_used_conf = max(set(row.conf_id_list), key=row.conf_id_list.count)
        row.confs = ", ".join(list(set(row.conf_list)))
        row.groups = ", ".join(list(set(row2.group_list)))
        row.name = row.patient.last_name + " " + row.patient.first_name
        if row.patient.id in anon.keys() :
            try:
                ln = unicode(row.patient.last_name, 'utf-8')
            except UnicodeDecodeError:
                ln = row.patient.last_name
            row.name = ln[:3]

        
    ##sort result
    reverse = False
    if request.vars["reverse"] == "true" :
        reverse = True
    if request.vars["sort"] == "configs" :
        result = sorted(result, key = lambda row : row.confs, reverse=reverse)
    elif request.vars["sort"] == "groups" :
        result = sorted(result, key = lambda row : row.groups, reverse=reverse)
    elif request.vars["sort"] == "files" :
        result = sorted(result, key = lambda row : row[count], reverse=reverse)
    elif "sort" in request.vars:
        result = sorted(result, key = lambda row : row.patient[request.vars["sort"]], reverse=reverse)
    
    ##filter
    if "filter" not in request.vars :
        request.vars["filter"] = ""
        
    for row in result :
        row.string = (row.confs+row.groups+row.patient.last_name+row.patient.first_name+str(row.patient.birth)).lower()+str(row.patient.info)
    result = filter(lambda row : vidjil_utils.filter(row.string,request.vars["filter"]), result )

    return dict(query = result,
                count = count,
                isAdmin = isAdmin,
                reverse = reverse)



## return form to create new patient
def add(): 
    if (auth.has_permission('create', 'patient') ):
        return dict(message=T('add patient'))
    else :
        res = {"message": ACCESS_DENIED}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))



## create a patient if the html form is complete
## need ["first_name", "last_name", "birth_date", "info"]
## redirect to patient list if success
## return a flash error message if fail
def add_form(): 
    if (auth.has_permission('create', 'patient') ):
        
        error = ""
        if request.vars["first_name"] == "" :
            error += "first name needed, "
        if request.vars["last_name"] == "" :
            error += "last name needed, "
        try:
            datetime.datetime.strptime(""+request.vars['birth'], '%Y-%m-%d')
        except ValueError:
            error += "date missing or wrong format"

        if error=="" :
            id = db.patient.insert(first_name=request.vars["first_name"],
                                   last_name=request.vars["last_name"],
                                   birth=request.vars["birth"],
                                   info=request.vars["info"],
                                   id_label=request.vars["id_label"],
                                   creator=auth.user_id)


            user_group = auth.user_group(auth.user.id)
            admin_group = db(db.auth_group.role=='admin').select().first().id
            
            #patient creator automaticaly has all rights 
            auth.add_permission(user_group, 'admin', db.patient, id)
            auth.add_permission(user_group, 'read', db.patient, id)
            auth.add_permission(user_group, 'anon', db.patient, id)
            
            patient_name = request.vars["first_name"] + ' ' + request.vars["last_name"]

            res = {"redirect": "patient/info",
                   "args" : { "id" : id },
                   "message": patient_name + ": patient added"}
            log.info(res)
            return gluon.contrib.simplejson.dumps(res, separators=(',',':'))

        else :
            res = {"success" : "false",
                   "message" : error}
            log.error(res)
            return gluon.contrib.simplejson.dumps(res, separators=(',',':'))
        
    else :
        res = {"message": ACCESS_DENIED}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))



## return edit form 
def edit(): 
    if (auth.has_permission('admin', 'patient', request.vars["id"]) ):
        return dict(message=T('edit patient'))
    else :
        res = {"message": ACCESS_DENIED}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))



## check edit form
## need ["first_name", "last_name", "birth_date", "info"]
## redirect to patient list if success
## return a flash error message if fail
def edit_form(): 
    if (auth.has_permission('admin', 'patient', request.vars["id"]) ):
        error = ""
        if request.vars["first_name"] == "" :
            error += "first name needed, "
        if request.vars["last_name"] == "" :
            error += "last name needed, "
        try:
            datetime.datetime.strptime(""+request.vars['birth'], '%Y-%m-%d')
        except ValueError:
            error += "date missing or wrong format"
        if request.vars["id"] == "" :
            error += "patient id needed, "

        if error=="" :
            db.patient[request.vars["id"]] = dict(first_name=request.vars["first_name"],
                                                   last_name=request.vars["last_name"],
                                                   birth=request.vars["birth"],
                                                   info=request.vars["info"],
                                                   id_label=request.vars["id_label"]
                                                   )

            res = {"redirect": "back",
                   "message": "%s %s (%s): patient edited" % (request.vars["first_name"], request.vars["last_name"], request.vars["id"])}
            log.info(res)
            return gluon.contrib.simplejson.dumps(res, separators=(',',':'))

        else :
            res = {"success" : "false", "message" : error}
            log.error(res)
            return gluon.contrib.simplejson.dumps(res, separators=(',',':'))
    else :
        res = {"message": ACCESS_DENIED}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))


def download():
    return response.download(request, db)


#
def confirm():
    if (auth.has_permission('admin', 'patient', request.vars["id"]) ):
        log.debug('request patient deletion')
        return dict(message=T('confirm patient deletion'))
    else :
        res = {"message": ACCESS_DENIED}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))


#
def delete():
    if (auth.has_permission('admin', 'patient', request.vars["id"]) ):
        import shutil, os.path
        #delete data file 
        query = db( (db.sequence_file.patient_id==request.vars["id"])).select() 
        for row in query :
            db(db.results_file.sequence_file_id == row.id).delete()

        #delete sequence file
        db(db.sequence_file.patient_id == request.vars["id"]).delete()

        #delete patient
        db(db.patient.id == request.vars["id"]).delete()

        res = {"redirect": "patient/index",
               "success": "true",
               "message": "patient ("+str(request.vars["id"])+") deleted"}
        log.info(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))
    else :
        res = {"message": ACCESS_DENIED}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))

    
#
def permission(): 
    if (auth.has_permission('admin', 'patient', request.vars["id"]) ):
        
        query = db( db.auth_group.role != 'admin' ).select()
        
        for row in query :
            row.owner = row.role
            if row.owner[:5] == "user_" :
                id = int(row.owner[5:])
                row.owner = db.auth_user[id].first_name + " " + db.auth_user[id].last_name 

            row.admin = False
            if db(   (db.auth_permission.name == "admin")
                  & (db.auth_permission.record_id == request.vars["id"])
                  & (db.auth_permission.group_id == row.id)
                  & (db.auth_permission.table_name == db.patient)
              ).count() > 0 :
                row.admin = True
                
            row.anon = False
            if db(   (db.auth_permission.name == "anon")
                  & (db.auth_permission.record_id == request.vars["id"])
                  & (db.auth_permission.group_id == row.id)
                  & (db.auth_permission.table_name == db.patient)
              ).count() > 0 :
                row.anon = True
                
            row.read = False
            if db(   (db.auth_permission.name == "read")
                  & (db.auth_permission.record_id == request.vars["id"])
                  & (db.auth_permission.group_id == row.id)
                  & (db.auth_permission.table_name == db.patient)
              ).count() > 0 :
                row.read = True
        
        return dict(query=query)
    else :
        res = {"message": ACCESS_DENIED}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))


#
def change_permission():
    if (auth.has_permission('admin', 'patient', request.vars["patient_id"]) ):
        error = ""
        if request.vars["group_id"] == "" :
            error += "missing group_id, "
        if request.vars["patient_id"] == "" :
            error += "missing patient_id, "
        if request.vars["permission"] == "" :
            error += "missing permission, "

        if error=="":
            if db(   (db.auth_permission.name == request.vars["permission"])
                      & (db.auth_permission.record_id == request.vars["patient_id"])
                      & (db.auth_permission.group_id == request.vars["group_id"])
                      & (db.auth_permission.table_name == db.patient)
                  ).count() > 0 :
                auth.del_permission(request.vars["group_id"], request.vars["permission"], db.patient, request.vars["patient_id"])
                res = {"message" : "access '%s' deleted to '%s'" % (request.vars["permission"], db.auth_group[request.vars["group_id"]].role)}
            else :
                auth.add_permission(request.vars["group_id"], request.vars["permission"], db.patient, request.vars["patient_id"])
                res = {"message" : "access '%s' granted to '%s'" % (request.vars["permission"], db.auth_group[request.vars["group_id"]].role)}
            
            log.info(res)
            return gluon.contrib.simplejson.dumps(res, separators=(',',':'))
        else :
            res = {"message": "incomplete request : "+error }
            log.error(res)
            return gluon.contrib.simplejson.dumps(res, separators=(',',':'))
    else :
        res = {"message": ACCESS_DENIED}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))
