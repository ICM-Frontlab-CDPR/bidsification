from math import isnan
import pandas as pd


root = '/home/hippolytedreyfus/Documents/explore_plus/Data/bidsification/'

participants_file = root + 'list_participants.xlsx'
tsv_file = root + 'participants_to_import.tsv'

df_in = pd.read_excel(participants_file)
#df_out = pd.DataFrame(columns=['participant_id', 'NIP', 'infos_participant','session_label', 'acq_date', 'acq_label','location','run_id','to_import'])
columns = df_in.keys()
subject_ids = df_in["participant_id"]
subject_filter = subject_ids.duplicated(keep='first')
subject_ids = subject_ids[subject_filter==False].values
rows_list = []
for id in subject_ids:
    print(id) 
    #how many sessions
    subj_df = df_in[df_in["participant_id"]==id]
    sess_labels = subj_df["session_label"]
    sess_filter = sess_labels.duplicated(keep='first')
    sess_labels = sess_labels[sess_filter==False].values
    for sess in sess_labels:
        sess_df = subj_df[subj_df["session_label"]==sess]
        to_import = []
        print(sess_df.shape[0])
        for i in range(sess_df.shape[0]):
            row = sess_df.iloc[i]    
            print(id, sess,row['run_id'],row['data_type']) 
            fid = row['fid']
            data_type = row['data_type']
            if 'anat' in data_type:
                if isnan(row['run_id']): 
                    filename = id+'_ses-%02d' % sess+'_acq-'+row['seq_type']+'_'+row['contrast_type'] 
                    print(filename, "\n")
                else:
                    filename = id+'_ses-%02d' % sess+'_acq-'+row['seq_type']+'_run-%02d' % row['run_id']+'_'+row['contrast_type'] 
                    print(filename, "\n")
            if 'func' in data_type:
                if isnan(row['run_id']):
                    filename = id+'_ses-%02d' % sess+'_task-'+row['task_type']+'_acq-'+row['seq_type']+'_dir-'+row['encoding_dir']+'_'+row['contrast_type']
                    print(filename,"\n")
                else:     
                    filename = id+'_ses-%02d' % sess+'_task-'+row['task_type']+'_acq-'+row['seq_type']+'_dir-'+row['encoding_dir']+'_run-%02d' % row['run_id']+'_'+row['contrast_type'] 
                    print(filename,"\n")
            if 'fmap' in data_type: 
                if isnan(row['run_id']):
                    filename = id+'_ses-%02d' % sess+'_acq-'+row['seq_type']+'_dir-'+row['encoding_dir']+'_'+row['contrast_type']
                    print(filename,"\n")
                else:     
                    filename = id+'_ses-%02d' % sess+'_acq-'+row['seq_type']+'_dir-'+row['encoding_dir']+'_run-%02d' % row['run_id']+'_'+row['contrast_type']
                    print(filename,"\n")
            to_import.append((str(fid),data_type,(filename)))
        #print(to_import)
        rows_list.append({'participant_id':id,
                       'NIP':row['NIP'],
                       'infos_participant':row['infos_participant'],
                       'session_label':row['session_label'],
                       'acq_date':str(row['acq_date']).split(sep=' ')[0], 
                       'acq_label':row['acq_label'],
                       'location':row['location'],
                       'run_id':float("nan"),
                       'to_import':tuple(to_import)})
#print(rows_list)           
df_out = pd.DataFrame(rows_list)
df_out.to_csv(tsv_file, 
              sep='\t', index=False, header=True)
