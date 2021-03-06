from .models import CalculoModelo, Etp, UnidadHidrologica, Pcp
from .serializers import CalculoModeloSerializer, UnidadHidrologicaSerializer, DatosGeneradosUnidadSerializer
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from django.shortcuts import render, redirect
from django.views.generic import ListView
from django.http import JsonResponse
from decimal import *
import json

#API Rest
@swagger_auto_schema(methods=['POST'], request_body=DatosGeneradosUnidadSerializer, responses={200: CalculoModeloSerializer})
@api_view(['POST'])
def calculoModelo(request):
    """
        Realiza el calculo del modelo hidrologico con los datos de entrada
    """
    if request.method == 'POST':
        
        serializer = DatosGeneradosUnidadSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        try:
            calculoModelo = ejecutarCalculo(serializer.data)
        except Exception as e:
            return JsonResponse({'detail':str(e)},status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        serializerCalculo = CalculoModeloSerializer(data=calculoModelo, many=True)
        serializerCalculo.is_valid(raise_exception=True)

        serializerCalculo.save()
        serializer.save()

        return JsonResponse(serializerCalculo.data, status=status.HTTP_201_CREATED, safe=False)

@swagger_auto_schema(methods=['GET'],responses={200: CalculoModeloSerializer})
@api_view(['GET'])
def calculoModeloUnidad(request,unidad_id):
    if request.method == 'GET':
        unidad = UnidadHidrologica.objects.get(Id=unidad_id)
        calculoModelo = CalculoModelo.objects.filter(Unidad=unidad).order_by('-fecha')[:15]
        serializer = CalculoModeloSerializer(data=calculoModelo, many=True)
        serializer.is_valid(raise_exception=False)

        return JsonResponse(serializer.data, status=status.HTTP_201_CREATED, safe=False)



def ejecutarCalculo(data):
    calculo = []
    unidad = UnidadHidrologica.objects.get(Id=data[0]['Unidad'])
    calculoLast = CalculoModelo.objects.all().last()
    
    if calculoLast != None:
        calculo.append(calculoLast.toJson())

    i = 0
    while i < len(data):
        dp = Decimal(data[i]['Pcp'])
        if len(calculo) < 1:
            calculo_nuevo = True
        else:
            calculo_nuevo = False    

        if(dp != 0):
            if(calculo_nuevo):
                dQ = (unidad.Bh_Pcorr * dp)*pow(unidad.Cs_Ssm/unidad.Bh_FC,unidad.Bh_Beta)
            else:
                dQ = (unidad.Bh_Pcorr * dp)*pow(Decimal(calculo[-1]['SSm'])/pow(unidad.Bh_FC,unidad.Bh_Beta),unidad.Bh_Beta)       
        else:    
            dQ = 0

        if(calculo_nuevo):
            ssm = unidad.Cs_Ssm + (dp - dQ)
        else:
            ssm = calculo[-1]['SSm'] + (dp - dQ)

        duz = dQ

        if(ssm >= (unidad.Bh_LP*unidad.Bh_FC)):
            eact = Decimal(data[i]['Etp'])
        else:
            eact = (ssm * Decimal(data[i]['Etp']))/(unidad.Bh_LP*unidad.Bh_FC)

        cambioSsm = ssm - eact

        if(calculo_nuevo):
            Suz = unidad.Cs_Suz
        else:
            Suz = calculo[-1]['Delta_Suz'] + calculo[-1]['duz'] - calculo[-1]['Q1'] - calculo[-1]['Q0'] - calculo[-1]['Q2'] - calculo[-1]['Q3']

        if(Suz >= unidad.HeI_PERC):
            perc = unidad.HeI_PERC
        else:
            perc = Suz

        cambioSuz = Suz - perc

        if(calculo_nuevo):
            SIz = unidad.Cs_SIz + perc       
        else:
            SIz = calculo[-1]['Delta_SIz'] + perc

        if(Suz > unidad.Cs_UZL0):
            q0 = unidad.Hes_K0*(cambioSuz-unidad.Cs_UZL0)  
        else:
            q0 = 0

        q1 = unidad.Hes_K1*(cambioSuz-unidad.Cs_UZL0)    
        q2 = unidad.Hes_K2*(cambioSuz-unidad.Cs_UZL1)  
        q3 = unidad.Hes_K3*(cambioSuz-unidad.Cs_UZL2)  

        cambioSuzPrima = cambioSuz - q0 - q1 - q2 - q3
        q4 = unidad.Hes_K3*SIz

        qgen = q0 - q1 + q2 + q3 + q4
        qf = (qgen*unidad.Hd_Area)/Decimal('86.4')

        cambioSIz = SIz-q4
        almac = dp-eact-qgen
        humSuelo = (cambioSsm-ssm)+(cambioSuzPrima-cambioSuz)+(cambioSIz-SIz) 

        balance = almac - humSuelo        

        calculoModelo = CalculoModelo(Unidad=unidad, fecha=data[i]['Fecha'], p_ajustada=round(dp,2),
            dQ=round(dQ,2), duz=round(duz,2), SSm=round(ssm,2), ETR=round(eact,2), Delta_ssm=round(cambioSsm,2), SUZ2=round(Suz,2), Perc=round(perc,2), 
            Delta_Suz=round(cambioSuz,2), SIz=round(SIz,2), Q0=round(q0,2), Q1=round(q1,2), Q2=round(q2,2), Q3=round(q3,2), Delta_Suz_prima=round(cambioSuzPrima,2),
            Q4=round(q4,2), Q_gen=round(qgen,2), Caudal=round(qf,2), Delta_SIz=round(cambioSIz,2))
        
        calculo.append(calculoModelo.toJson())

        i = i + 1  

    return calculo       



#Views API REST
class CalculoModeloViewSet(viewsets.ModelViewSet):
    queryset = CalculoModelo.objects.all()
    serializer_class = CalculoModeloSerializer

class UnidadHidrologicaViewSet(viewsets.ModelViewSet):
    queryset = UnidadHidrologica.objects.all()
    serializer_class = UnidadHidrologicaSerializer    




# Create your views here.
class CalculoModeloListView(ListView):
    model = CalculoModelo
    context_object_name = 'calculo_list'   # your own name for the list as a template variable
    template_name = 'modelo_datos.html'

def load_unidad_hidro(request, *args, **kwargs):
    Id=[]
    unidades = UnidadHidrologica.objects.all().order_by('Id')
    for unidad in unidades:
        Id.append(unidad.Id)
    data = {
        "unidades": Id      
    }
    return JsonResponse(data,safe=False) 

def get_calculo_data(request, *args, **kwargs):
    unidad = UnidadHidrologica.objects.get(Id=request.GET.get('unidad'))
    labels = []
    caudal_items = []
    p_ajustada_items = []
    for calculo in CalculoModelo.objects.filter(Unidad=unidad, fecha__gt = request.GET.get('fecha')).order_by('fecha')[:15]:
        labels.append(calculo.fecha)
        caudal_items.append(calculo.Caudal)
        p_ajustada_items.append(calculo.p_ajustada)
    data = {
        "labels": labels,
        "caudal_items": caudal_items,  
        "p_ajustada_items": p_ajustada_items      
    }
        
    return JsonResponse(data,safe=False)    

def load_file_view(request):
    return render(request, 'load_file.html')

def load_data_file(request, *args, **kwargs):
    if(request.method == 'POST'):
        load_data = json.loads(request.body)
        unidad = UnidadHidrologica.objects.get(Id=load_data[0]['Unidad'])
        for registro in load_data:
            etp = Etp(Unidad=unidad, Fecha=registro['Fecha'], Etp=registro['ETP'])
            etp.save()
            pcp = Pcp(Unidad=unidad, Fecha=registro['Fecha'], Pcp=registro['PCP'])
            pcp.save()

    return render(request, 'load_file.html')

def create_data(request, *args, **kwargs):
    data = []

    etpList = Etp.objects.all()
    pcpList = Pcp.objects.all()

    print(etpList[0].Unidad.Id)
    unidad = UnidadHidrologica.objects.get(Id=etpList[0].Unidad.Id)

    i = 0
    while i < len(pcpList):
        dp = pcpList[i].Pcp

        calculoLast = CalculoModelo.objects.all().last()
        if(calculoLast == None):
            firtsFlag = True
        else:
            firtsFlag = False

        if(dp != 0):
            if(firtsFlag):
                dQ = (unidad.Bh_Pcorr * dp)*pow(unidad.Cs_Ssm/unidad.Bh_FC,unidad.Bh_Beta)
            else:
                dQ = (unidad.Bh_Pcorr * dp)*pow(calculoLast.SSm/pow(unidad.Bh_FC,unidad.Bh_Beta),unidad.Bh_Beta)       
        else:    
            dQ = 0

        if(firtsFlag):
            ssm = unidad.Cs_Ssm + (dp - dQ)
        else:
            ssm = calculoLast.SSm + (dp - dQ)    

        duz = dQ

        if(ssm >= (unidad.Bh_LP*unidad.Bh_FC)):
            eact = etpList[i].Etp
        else:
            eact = (ssm * etpList[i].Etp)/(unidad.Bh_LP*unidad.Bh_FC)

        cambioSsm = ssm - eact

        if(firtsFlag):
            Suz = unidad.Cs_Suz
        else:
            Suz = calculoLast.Delta_Suz + calculoLast.duz - calculoLast.Q1 - calculoLast.Q0 - calculoLast.Q2 - calculoLast.Q3

        if(Suz >= unidad.HeI_PERC):
            perc = unidad.HeI_PERC
        else:
            perc = Suz

        cambioSuz = Suz - perc

        if(firtsFlag):
            SIz = unidad.Cs_SIz + perc       
        else:
            SIz = calculoLast.Delta_SIz + perc

        if(Suz > unidad.Cs_UZL0):
            q0 = unidad.Hes_K0*(cambioSuz-unidad.Cs_UZL0)  
        else:
            q0 = 0

        q1 = unidad.Hes_K1*(cambioSuz-unidad.Cs_UZL0)    
        q2 = unidad.Hes_K2*(cambioSuz-unidad.Cs_UZL1)  
        q3 = unidad.Hes_K3*(cambioSuz-unidad.Cs_UZL2)  

        cambioSuzPrima = cambioSuz - q0 - q1 - q2 - q3
        q4 = unidad.Hes_K3*SIz

        qgen = q0 - q1 + q2 + q3 + q4
        qf = (qgen*unidad.Hd_Area)/Decimal('86.4')

        cambioSIz = SIz-q4
        almac = dp-eact-qgen
        humSuelo = (cambioSsm-ssm)+(cambioSuzPrima-cambioSuz)+(cambioSIz-SIz) 

        balance = almac - humSuelo

        calculoModelo = CalculoModelo(Unidad=unidad, fecha=pcpList[i].Fecha, p_ajustada=round(dp,2),
            dQ=round(dQ,2), duz=round(duz,2), SSm=round(ssm,2), ETR=round(eact,2), Delta_ssm=round(cambioSsm,2), SUZ2=round(Suz,2), Perc=round(perc,2), 
            Delta_Suz=round(cambioSuz,2), SIz=round(SIz,2), Q0=round(q0,2), Q1=round(q1,2), Q2=round(q2,2), Q3=round(q3,2), Delta_Suz_prima=round(cambioSuzPrima,2),
            Q4=round(q4,2), Q_gen=round(qgen,2), Caudal=round(qf,2), Delta_SIz=round(cambioSIz,2))
        calculoModelo.save()    
        i = i + 1
        data.append(CalculoModelo.toJson(calculoModelo))

    return JsonResponse({'calculo':data},status=200)
