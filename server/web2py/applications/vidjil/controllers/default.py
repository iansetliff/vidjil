# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This is a sample controller
## - index is the default action of any application
## - user is required for authentication and authorization
## - download is for downloading files uploaded in the db (does streaming)
## - call exposes all registered services (none by default)
#########################################################################

import defs
import vidjil_utils

import gluon.contrib.simplejson, time, datetime
if request.env.http_origin:
    response.headers['Access-Control-Allow-Origin'] = request.env.http_origin
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Max-Age'] = 86400

#########################################################################
##return the default index page for vidjil (empty)
def index():
    """
    example action using the internationalization operator T and flash
    rendered by views/default/index.html or views/generic.html

    if you need a simple wiki simply replace the two lines below with:
    return auth.wiki()
    """
    response.flash = T("Welcome to Vidjil!")
    return dict(message=T('hello world'))

#########################################################################
##return the view default/help.html
def help():
    return dict(message=T('help i\'m lost'))

#########################################################################
## add a scheduller task to run vidjil on a specific sequence file
# need sequence_file_id, config_id
# need patient admin permission
def run_request():
    error = ""

    ##TODO check
    if not "sequence_file_id" in request.vars :
        error += "id sequence file needed, "
    if not "config_id" in request.vars:
        error += "id config needed, "
    if not auth.has_permission("run", "results_file") :
        error += "permission needed"

    id_patient = db.sequence_file[request.vars["sequence_file_id"]].patient_id

    if not auth.has_permission('admin', 'patient', id_patient) :
        error += "you do not have permission to launch process for this patient ("+str(id_patient)+"), "

    if error == "" :
        res = schedule_run(request.vars["sequence_file_id"], request.vars["config_id"])
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))

    else :
        res = {"success" : "false",
               "message" : "default/run_request : " + error}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))



#########################################################################
## return .data file
# need patient, config
# need patient admin or read permission
def get_data():
    import time
    from subprocess import Popen, PIPE, STDOUT
    if not auth.user :
        res = {"redirect" : URL('default', 'user', args='login', scheme=True, host=True,
                            vars=dict(_next=URL('default', 'get_data', scheme=True, host=True,
                                                vars=dict(patient = request.vars["patient"],
                                                          config =request.vars["config"]))
                                      )
                            )}
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))

    error = ""

    if not "patient" in request.vars :
        error += "id patient file needed, "
    if not "config" in request.vars:
        error += "id config needed, "
    if not auth.has_permission('admin', 'patient', request.vars["patient"]) and \
    not auth.has_permission('read', 'patient', request.vars["patient"]):
        error += "you do not have permission to consult this patient ("+request.vars["patient"]+")"

    query = db( ( db.fused_file.patient_id == request.vars["patient"] )
               & ( db.fused_file.config_id == request.vars["config"] )
               ).select()
    for row in query :
        fused_file = defs.DIR_RESULTS+'/'+row.fused_file
        sequence_file_list = row.sequence_file_list

    if not 'fused_file' in locals():
        error += "file not found"

    if error == "" :

        f = open(fused_file, "r")
        data = gluon.contrib.simplejson.loads(f.read())
        f.close()
        
        patient_name = vidjil_utils.anon(request.vars["patient"], auth.user_id)
        config_name = db.config[request.vars["config"]].name
        
        data["patient_name"] = patient_name
        data["config_name"] = config_name
        data["dataFileName"] = patient_name + " (" + config_name + ")"
        data["info"] = db.patient(request.vars["patient"]).info
        data["samples"]["original_names"] = []
        data["samples"]["timestamp"] = []
        data["samples"]["info"] = []

        ## récupération des infos stockées sur la base de données
        if sequence_file_list is not None:
            sequence_file_list = sequence_file_list.split("_")
            for i in range(len(sequence_file_list)-1):
                row = db( db.sequence_file.id == int(sequence_file_list[i]) ).select().first()
                if row is not None:
                    data["samples"]["original_names"].append(row.filename)
                    data["samples"]["timestamp"].append(str(row.sampling_date))
                    data["samples"]["info"].append(row.info)
                else :
                    data["samples"]["original_names"].append("unknow")
                    data["samples"]["timestamp"].append("")
                    data["samples"]["info"].append("")

        else :
            ## old method
            query = db( ( db.patient.id == db.sequence_file.patient_id )
                       & ( db.results_file.sequence_file_id == db.sequence_file.id )
                       & ( db.patient.id == request.vars["patient"] )
                       & ( db.results_file.config_id == request.vars["config"]  )
                       ).select( orderby=db.sequence_file.id|db.results_file.run_date, groupby=db.sequence_file.id )

            for row in query :
                filename = row.sequence_file.filename
                data["samples"]["original_names"].append(filename)
                data["samples"]["timestamp"].append(str(row.sequence_file.sampling_date))
                data["samples"]["info"].append(row.sequence_file.info)

        log.debug("get_data: %s -> %s" % (request.vars["patient"], fused_file))
        return gluon.contrib.simplejson.dumps(data, separators=(',',':'))

    else :
        res = {"success" : "false",
               "message" : "default/get_data : " + error}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))
    
#########################################################################
def get_custom_data():
    import time
    import vidjil_utils
    from subprocess import Popen, PIPE, STDOUT
    if not auth.user :
        res = {"redirect" : URL('default', 'user', args='login', scheme=True, host=True)} #TODO _next
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))

    error = ""

    if not "custom" in request.vars :
        error += "no file selected, "
    else:
        for id in request.vars["custom"] :
            sequence_file_id = db.results_file[id].sequence_file_id
            patient_id =db.sequence_file[sequence_file_id].patient_id
            if not auth.has_permission('admin', 'patient', patient_id) and \
                not auth.has_permission('read', 'patient', patient_id):
                error += "you do not have permission to consult this patient ("+str(patient_id)+")"
            
    if error == "" :
        data = custom_fuse(request.vars["custom"])
        
        data["dataFileName"] = "custom"
        data["info"] = "custom"
        data["samples"]["original_names"] = []
        data["samples"]["timestamp"] = []
        data["samples"]["info"] = []
        
        for id in request.vars["custom"] :
            sequence_file_id = db.results_file[id].sequence_file_id
            patient_id = db.sequence_file[sequence_file_id].patient_id
            patient_name = vidjil_utils.anon(patient_id, auth.user_id)
            filename = db.sequence_file[sequence_file_id].filename
            data["samples"]["original_names"].append(patient_name + "_" + filename)
            data["samples"]["timestamp"].append(str(db.sequence_file[sequence_file_id].sampling_date))
            data["samples"]["info"].append(db.sequence_file[sequence_file_id].info)

        return gluon.contrib.simplejson.dumps(data, separators=(',',':'))

    else :
        res = {"success" : "false",
               "message" : "default/get_custom_data : " + error}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))
    
#########################################################################
## return .analysis file
# need patient_id, config_id
# need patient admin or read permission
def get_analysis():
    error = ""

    if not "patient" in request.vars :
        error += "id patient file needed, "
    if not "config" in request.vars:
        error += "id config needed, "
    if not auth.has_permission('admin', 'patient', request.vars["patient"]) and \
    not auth.has_permission('read', 'patient', request.vars["patient"]):
        error += "you do not have permission to consult this patient ("+request.vars["patient"]+")"

    ## empty analysis file
    res = {"samples": {"number": 0,
                      "original_names": [],
                      "order": [],
                      "info_sequence_file" : []
                       },
           "custom": [],
           "clusters": [],
           "clones" : [],
           "tags": {},
           "vidjil_json_version" : "2014.09"
           }


    if error == "" :

        ## récupération des infos se trouvant dans le fichier .analysis
        analysis_query = db(  (db.analysis_file.patient_id == request.vars["patient"])
                   & (db.analysis_file.config_id == request.vars["config"] )  )

        if not analysis_query.isempty() :
            row = analysis_query.select().first()
            f = open(defs.DIR_RESULTS+'/'+row.analysis_file, "r")
            analysis = gluon.contrib.simplejson.loads(f.read())
            f.close()
            if 'cluster' in analysis:
                res["clusters"] = analysis["cluster"]
            if 'clusters' in analysis :
                res["clusters"] = analysis["clusters"]
            res["clones"] = analysis["clones"]
            res["tags"] = analysis["tags"]
            res["samples"]= analysis["samples"]

        res["info_patient"] = db.patient[request.vars["patient"]].info
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))

    else :
        res = {"success" : "false",
               "message" : "default/get_analysis : " + error}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))


#########################################################################
## upload .analysis file and store it on the database
# need patient_id, config_id, fileToUpload
# need patient admin permission
def save_analysis():
    error = ""

    if not "patient" in request.vars :
        error += "id patient file needed, "
    if not "config" in request.vars:
        error += "id config needed, "
    if not auth.has_permission('admin', 'patient', request.vars['patient']) :
        error += "you do not have permission to save changes on this patient"

    if error == "" :
        analysis_query = db(  (db.analysis_file.patient_id == request.vars['patient'])
                            & (db.analysis_file.config_id == request.vars['config'] )  )

        f = request.vars['fileToUpload']

        ts = time.time()
        if not analysis_query.isempty() :
            analysis_id = analysis_query.select().first().id
            db.analysis_file[analysis_id] = dict(analysis_file = db.analysis_file.analysis_file.store(f.file, f.filename),
                                                 analyze_date = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                                                 )
        else:

            analysis_id = db.analysis_file.insert(analysis_file = db.analysis_file.analysis_file.store(f.file, f.filename),
                                                  config_id = request.vars['config'],
                                                  patient_id = request.vars['patient'],
                                                  analyze_date = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                                                  )

        patient_name = db.patient[request.vars['patient']].first_name + " " + db.patient[request.vars['patient']].last_name

        res = {"success" : "true",
               "message" : patient_name+": analysis saved"}
        log.info(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))
    else :
        res = {"success" : "false",
               "message" : error}
        log.error(res)
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))



#########################################################################
## TODO make custom download for .data et .analysis
@cache.action()
def download():
    """
    allows downloading of uploaded files
    http://..../[app]/default/download/[filename]
    """
    return response.download(request, db, download_filename=request.vars.filename)

def download_data():

    file = "test"
    return response.stream( file, chunk_size=4096, filename=request.vars.filename)

#########################################################################
##
def create_self_signed_cert(cert_dir):
    """
    create a new self-signed cert and key and write them to disk
    """
    from OpenSSL import crypto, SSL
    from socket import gethostname
    from pprint import pprint
    from time import gmtime, mktime
    from os.path import exists, join

    CERT_FILE = "ssl_certificate.crt"
    KEY_FILE = "ssl_self_signed.key"
    ssl_created = False
    if not exists(join(cert_dir, CERT_FILE)) \
            or not exists(join(cert_dir, KEY_FILE)):
        ssl_created = True
        # create a key pair
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 4096)

        # create a self-signed cert
        cert = crypto.X509()
        cert.get_subject().C = "AQ"
        cert.get_subject().ST = "State"
        cert.get_subject().L = "City"
        cert.get_subject().O = "Company"
        cert.get_subject().OU = "Organization"
        cert.get_subject().CN = gethostname()
        cert.set_serial_number(1000)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10*365*24*60*60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, 'sha1')

        open(join(cert_dir, CERT_FILE), "wt").write(
            crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        open(join(cert_dir, KEY_FILE), "wt").write(
            crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

        create_self_signed_cert('.')

    return(ssl_created, cert_dir, CERT_FILE, KEY_FILE)


#########################################################################
def handle_error():
    """
    Custom error handler that returns correct status codes,
    adapted from http://www.web2pyslices.com/slice/show/1529/custom-error-routing
    """

    code = request.vars.code
    request_url = request.vars.request_url
    ticket = request.vars.ticket

    log.error("[%s] %s" % (code, ticket))

    if code is not None and request_url != request.url:# Make sure error url is not current url to avoid infinite loop.
        response.status = int(code) # Assign the error status code to the current response. (Must be integer to work.)

    if code == '403':
        return "Not authorized"
    elif code == '404':
        return "Not found"
    elif code == '500':
        # Get ticket URL:
        ticket_url = "<a href='%(scheme)s://%(host)s/admin/default/ticket/%(ticket)s' target='_blank'>%(ticket)s</a>" % {'scheme':'https','host':request.env.http_host,'ticket':ticket}

        # Email a notice, etc:
        mail.send(to=['contact@vidjil.org'],
                  subject="[Vidjil] web2py error",
                  message="Error Ticket:  %s" % ticket_url)

    return "Server error"





#########################################################################
##TODO remove useless function ( maybe used by web2py internally )



#########################################################################
##not used
def call():
    """
    exposes services. for example:
    http://..../[app]/default/call/jsonrpc
    decorate with @services.jsonrpc the functions to expose
    supports xml, json, xmlrpc, jsonrpc, amfrpc, rss, csv
    """
    return service()

#########################################################################
##not used
@auth.requires_signature()
def data():
    """
    http://..../[app]/default/data/tables
    http://..../[app]/default/data/create/[table]
    http://..../[app]/default/data/read/[table]/[id]
    http://..../[app]/default/data/update/[table]/[id]
    http://..../[app]/default/data/delete/[table]/[id]
    http://..../[app]/default/data/select/[table]
    http://..../[app]/default/data/search/[table]
    but URLs must be signed, i.e. linked with
      A('table',_href=URL('data/tables',user_signature=True))
    or with the signed load operator
      LOAD('default','data.load',args='tables',ajax=True,user_signature=True)
    """
    return dict(form=crud())

#########################################################################
## not used
@auth.requires_login()
@auth.requires_membership('admin')
def add_membership():
    response.title = ""

    user_query = db(db.auth_user).select()
    group_query = db(~(db.auth_group.role.like("user%"))).select()

    form = SQLFORM.factory(
        Field('user', requires=IS_IN_SET([r.id for r in user_query], labels=[r.first_name+" "+r.last_name for r in user_query])),
        Field('group', requires=IS_IN_SET([r.id for r in group_query], labels=[r.role for r in group_query]))
        )

    if form.validate():
        db.auth_membership.insert(user_id=form.vars.user,
                                  group_id=form.vars.group)
        response.flash = "membership added"

    return dict(form=form)

#########################################################################
## not used
def upload_file():
        import shutil, os.path

        try:
            # Get the file from the form
            f = request.vars['files[]']
            p = request.vars['patient_id[]']
            i = request.vars['info[]']
            d = request.vars['date[]']

            # Store file
            id = db.sequence_file.insert(data_file = db.sequence_file.data_file.store(f.file, f.filename))

            record = db.sequence_file[id]
            path_list = []
            path_list.append(request.folder)
            path_list.append('uploads')
            path_list.append(record['data_file'])
            size =  shutil.os.path.getsize(shutil.os.path.join(*path_list))

            db.sequence_file[id] = dict(size_file=size ,
                                        patient_id=p,
                                        sampling_date=d,
                                        info=i)

            File = db(db.sequence_file.id==id).select()[0]
            res = dict(files=[{"name": str(f.filename),
                               "size": size,
                               "url": URL(f='download', args=[File['data_file']])
                               }])

            return gluon.contrib.simplejson.dumps(res, separators=(',',':'))

        except:
            res = dict(files=[{"name": "kuik", "size": 0, "error": "fail!!" }])
            return gluon.contrib.simplejson.dumps(res, separators=(',',':'))

#########################################################################
## not used
def delete_file():
        try:
            id = request.args[0]
            query=db(db.sequence_file.id==id)
            patient_id=query.select()[0].patient_id
            query.delete()
            session.flash = "file deleted"
            redirect( URL(f='patient', args=[patient_id]) )
        except:
            redirect( URL(f='patient', args=[patient_id]) )


#########################################################################
## not used
def upload():
        return dict()

def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    http://..../[app]/default/user/manage_users (requires membership in
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    """

    if auth.user and request.args[0] == 'login' :
        res = {"redirect" : URL('patient', 'index', scheme=True, host=True)}
        return gluon.contrib.simplejson.dumps(res, separators=(',',':'))

    return dict(form=auth())
