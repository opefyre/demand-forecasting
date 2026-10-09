"""Explicit Iran input conventions; no inferred markets or synthetic calendar months."""
from datetime import date, datetime, timedelta, time, timezone
from decimal import Decimal, InvalidOperation
import math
import re
from zoneinfo import ZoneInfo

import pandas as pd
from persiantools import digits
from persiantools.jdatetime import JalaliDate


def latin(value):
    return digits.fa_to_en(digits.ar_to_fa(str(value))).strip()


def numeric(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('Use a finite numeric value; missing values are not zero.')
    text=latin(value).replace('٫','.').replace('٬',',')
    if ',' in text:
        if not re.fullmatch(r'[+-]?\d{1,3}(,\d{3})+(\.\d+)?',text):
            raise ValueError('Use consistent thousands separators and a decimal point.')
        text=text.replace(',','')
    try:
        result=Decimal(text)
    except InvalidOperation as exc:
        raise ValueError('Use a finite numeric value.') from exc
    if not result.is_finite() or not math.isfinite(float(result)):
        raise ValueError('Use a finite numeric value.')
    return result


def convention(payload):
    """Omitted controls retain legacy config hashes and Gregorian/UTC behavior."""
    result={}
    if 'calendar' in payload:
        if payload['calendar'] not in ('gregorian','jalali'):
            raise ValueError('Choose Gregorian or Persian (Jalali) dates.')
        result['calendar']=payload['calendar']
    if 'publication_timezone' in payload:
        if payload['publication_timezone'] not in ('UTC','Asia/Tehran'):
            raise ValueError('Choose UTC or Tehran for publication dates.')
        result['publication_timezone']=payload['publication_timezone']
    details=payload.get('factor_details')
    if details is not None:
        if not isinstance(details,dict):
            raise ValueError('Choose a valid factor type.')
        kind=details.get('kind')
        if kind=='exchange_rate':
            required={'kind','currency','market','side','amount_unit','quote_quantity'}
            if set(details)!=required:
                raise ValueError('Specify the FX currency, market, buy/sell basis, rial/toman and quote quantity.')
            currency=details['currency']
            if not isinstance(currency,str) or not re.fullmatch(r'[A-Z]{3}',currency) or currency in ('IRR','IRT'):
                raise ValueError('Enter a foreign currency code such as USD, EUR or CNY.')
            if details['market'] not in ('free_market','official','commercial','settlement','other'):
                raise ValueError('Choose the relevant FX market; it is not inferred from your location.')
            if details['side'] not in ('buy','sell','mid','settlement') or details['amount_unit'] not in ('rial','toman'):
                raise ValueError('Choose the quote basis and rial or toman.')
            quantity=numeric(details['quote_quantity'])
            if not 0<quantity<=1_000_000:
                raise ValueError('Quote quantity must be positive and no more than 1,000,000.')
            result['factor_details']={**details,'quote_quantity':float(quantity)}
        elif kind=='inflation':
            measure=details.get('measure')
            if measure not in ('cpi_index','monthly_change','year_on_year','annual_average'):
                raise ValueError('Choose CPI index, monthly change, year-on-year or annual-average inflation.')
            required={'kind','measure','base_year'} if measure=='cpi_index' else {'kind','measure'}
            if set(details)!=required:
                raise ValueError('Specify the inflation measure; a CPI index also needs its base year.')
            if measure=='cpi_index':
                year=latin(details['base_year'])
                if not re.fullmatch(r'\d{4}',year) or not 1200<=int(year)<=2100:
                    raise ValueError('Enter the CPI base year shown by the source.')
                details={**details,'base_year':year}
            result['factor_details']=dict(details)
        else:
            raise ValueError('Choose exchange rate or inflation; omit factor details for other series.')
    return result


def unit(config):
    details=config.get('factor_details',{})
    if details.get('kind')=='exchange_rate':
        return 'IRR per '+details['currency']
    if details.get('kind')=='inflation':
        return ('CPI index (base '+details['base_year']+' = 100)' if details['measure']=='cpi_index' else
                {'monthly_change':'% monthly change','year_on_year':'% year-on-year change',
                 'annual_average':'% annual-average change'}[details['measure']])
    return config.get('unit')


def input_date(value,calendar):
    if isinstance(value,datetime):
        if value.time()!=time():
            raise ValueError('Use dates without times.')
        value=value.date()
    if isinstance(value,date):
        if calendar=='jalali':
            raise ValueError('For Persian dates, use YYYY-MM-DD text, not Excel date cells.')
        return value
    if not isinstance(value,str):
        raise ValueError('Use YYYY-MM-DD dates.')
    text=latin(value)
    if calendar=='jalali':
        text=text.replace('/','-')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',text):
        raise ValueError('Use YYYY-MM-DD dates.')
    year,month,day=map(int,text.split('-'))
    if calendar=='jalali':
        if not 1200<=year<=1600:
            raise ValueError('Use a Persian year from 1200 to 1600.')
        return JalaliDate(year,month,day).to_gregorian()
    if year<1900:
        raise ValueError('Use Gregorian dates from 1900 onward, or select Persian dates.')
    return date(year,month,day)


def period_bounds(period,frequency,calendar):
    if calendar=='jalali':
        j=JalaliDate(period)
        last=JalaliDate.days_in_month(j.month,j.year)
        if frequency=='monthly':
            if j.day!=last:
                raise ValueError('Monthly Persian observations need the last day of the Persian month.')
            start=JalaliDate(j.year,j.month,1).to_gregorian()
        elif frequency=='annual':
            if j.month!=12 or j.day!=last:
                raise ValueError('Annual Persian observations need the last day of Esfand.')
            start=JalaliDate(j.year,1,1).to_gregorian()
        else:
            start=period
    else:
        if frequency=='monthly':
            if period!=(pd.Timestamp(period)+pd.offsets.MonthEnd(0)).date():
                raise ValueError('Monthly observations need the last day of the month.')
            start=period.replace(day=1)
        elif frequency=='annual':
            if (period.month,period.day)!=(12,31):
                raise ValueError('Annual observations need December 31 as the period end.')
            start=period.replace(month=1,day=1)
        else:
            start=period
    return start


def normalized_value(raw,config):
    result=numeric(raw)
    details=config.get('factor_details',{})
    if details.get('kind')=='exchange_rate':
        if result<=0:
            raise ValueError('Exchange rates must be greater than zero.')
        result=result*(10 if details['amount_unit']=='toman' else 1)/Decimal(str(details['quote_quantity']))
    elif details.get('kind')=='inflation':
        if details['measure']=='cpi_index' and result<=0:
            raise ValueError('CPI index values must be greater than zero.')
        if details['measure']!='cpi_index' and result < -100:
            raise ValueError('An inflation change cannot be below -100%.')
    if not math.isfinite(float(result)):
        raise ValueError('The converted value is too large.')
    if result!=0 and float(result)==0:
        raise ValueError('The value is too small to preserve accurately.')
    return float(result)


def released_at(day,zone):
    # End of the declared local day, converted to UTC. Historical DST uses IANA rules.
    return datetime.combine(day,time.max,ZoneInfo(zone)).astimezone(timezone.utc).isoformat()


def period_gaps(periods,frequency,calendar):
    if not periods:
        return []
    if calendar=='gregorian' or frequency=='daily':
        expected=pd.date_range(periods[0],periods[-1],freq={'daily':'D','monthly':'ME','annual':'YE'}[frequency])
        return sorted(set(expected.strftime('%Y-%m-%d'))-set(periods))
    first,last=JalaliDate(date.fromisoformat(periods[0])),JalaliDate(date.fromisoformat(periods[-1]))
    expected=[]
    start=first.year*12+first.month-1
    stop=last.year*12+last.month-1
    for ordinal in range(start,stop+1,1 if frequency=='monthly' else 12):
        year,month=divmod(ordinal,12);month+=1
        expected.append(JalaliDate(year,month,JalaliDate.days_in_month(month,year)).to_gregorian().isoformat())
    return sorted(set(expected)-set(periods))


def completed_jalali_month(gregorian_boundary):
    """Exact expected month, not the latest nonmissing value in an uploaded file."""
    j=JalaliDate(gregorian_boundary)
    end=JalaliDate(j.year,j.month,JalaliDate.days_in_month(j.month,j.year))
    if end.to_gregorian()>gregorian_boundary:
        previous=JalaliDate(j.year,j.month,1).to_gregorian()-timedelta(days=1)
        end=JalaliDate(previous)
    return end.to_gregorian().isoformat()


def summary(config):
    details=config.get('factor_details',{})
    return {'calendar':config.get('calendar','gregorian'),
            'publication_timezone':config.get('publication_timezone','UTC'),
            'original_amount_unit':details.get('amount_unit'),
            'output_unit':unit(config),'factor_details':details,
            'value_rule':('value × 10 ÷ quote quantity' if details.get('amount_unit')=='toman' else
                          'value ÷ quote quantity') if details.get('kind')=='exchange_rate' else 'No value conversion',
            'period_rule':'Original Persian period boundaries retained; not relabelled as Gregorian months.'
                          if config.get('calendar')=='jalali' else 'Original Gregorian periods retained.'}
