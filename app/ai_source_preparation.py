"""Read-only assistant handoff into the same reviewed live-factor workflow."""
from .factor_preparation import preparation_report
from .factor_imports import digest


class AssistantSourcePreparation:
    def __init__(self, run, datasets, factors, live, profiles):
        self.run,self.datasets,self.factors,self.live,self.profiles=run,datasets,factors,live,profiles

    def choices(self):
        if self.run.get('base_run_id') or self.run.get('scenario_name'):
            raise ValueError('Choose the original forecast before preparing factors.')
        return self.profiles.for_run(self.run)

    def preview(self, series_id):
        if series_id not in {p['series_id'] for p in self.choices()['profiles']}:
            raise ValueError('Choose an exact saved customer/product profile. Configure missing profiles in Customers.')
        return preparation_report(self.run,self.datasets,self.factors,self.live,
                                  {'profile_series_id':series_id},self.profiles)

    def proposal(self, series_id):
        report=self.preview(series_id)
        return {'kind':'factor_preparation','run_id':self.run['run_id'],'profile_series_id':series_id,
                'run_sha256':digest(self.run),'review_token':report['review_token'],
                'profile':report['profile'],'sources':[{'name':r['name'],'note':r['note'],
                    'can_prepare':r['can_prepare']} for r in report['recommendations']],
                'requires_review':True,'workflow_opened':False}

    def open(self, action):
        if action['run_id']!=self.run['run_id'] or action['run_sha256']!=digest(self.run):
            raise ValueError('The forecast changed. Ask to review sources again.')
        report=self.preview(action['profile_series_id'])
        if action['review_token']!=report['review_token']:
            raise ValueError('Profiles or sources changed. Ask to review the current sources again.')
        return {'workflow':'factor_preparation','run_id':self.run['run_id'],
                'profile_series_id':action['profile_series_id']}
