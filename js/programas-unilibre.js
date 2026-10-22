/* =====================================================================
   Oferta de pregrado — Universidad Libre, seccional Barranquilla
   Fuente única para el chat (index.html) y la pantalla de Programas.
   Valores de matrícula 2026 publicados en unilibre.edu.co; el valor
   definitivo es siempre el del recibo de matrícula.
===================================================================== */
(function(){
  "use strict";

  var REQ_SALUD = ['Formulario de inscripción (gratuito)','Certificado de las Pruebas Saber 11','Fotocopia del documento de identidad','Entrevista de admisión'];
  var REQ_GENERAL = ['Formulario de inscripción (gratuito)','Fotocopia del documento de identidad','Entrevista de admisión'];

  window.UL_FACULTADES = [
    'Ciencias de la Salud, Exactas y Naturales',
    'Derecho, Ciencias Políticas y Sociales',
    'Ingeniería',
    'Ciencias Económicas, Administrativas y Contables'
  ];

  window.UL_SEDES = ['Sede Principal','Sede Centro'];
  window.UL_SEDE_ALIASES = {
    'Sede Principal':['sede principal','km 7','kilometro 7','puerto colombia'],
    'Sede Centro':['sede centro','el centro','carrera 46']
  };

  window.UL_PROGRAMS = [
    { id:'medicina', nombre:'Medicina', titulo:'Médico(a)', snies:'1497',
      facultad:'Ciencias de la Salud, Exactas y Naturales', sedes:['Sede Principal'],
      modalidad:'Presencial', jornada:'Diurna', duracion:'12 semestres (incluye internado)',
      costo:'$21.526.000 COP',
      resumen:'Forma médicos con enfoque humanista, ético y social. La selección es por puntaje global Saber 11: con 330 puntos o más la admisión es automática.',
      requisitos:['Formulario de inscripción (gratuito)','Certificado de las Pruebas Saber 11','Fotocopia del documento de identidad'],
      aliases:['medicina','medico','ser doctor'] },
    { id:'fisioterapia', nombre:'Fisioterapia', titulo:'Fisioterapeuta', snies:'3436',
      facultad:'Ciencias de la Salud, Exactas y Naturales', sedes:['Sede Principal'],
      modalidad:'Presencial', jornada:'Diurna', duracion:'8 semestres',
      costo:'$6.636.000 COP',
      resumen:'Para quienes se interesan por la salud, el bienestar físico, la rehabilitación y el deporte.',
      requisitos:REQ_SALUD, aliases:['fisioterapia','fisioterapeuta','terapia fisica','rehabilitacion'] },
    { id:'bacteriologia', nombre:'Bacteriología', titulo:'Bacteriólogo(a)', snies:'53080',
      facultad:'Ciencias de la Salud, Exactas y Naturales', sedes:['Sede Principal'],
      modalidad:'Presencial', jornada:'Diurna', duracion:'9 semestres',
      costo:'$7.962.000 COP',
      resumen:'Laboratorio clínico, bancos de sangre, salud pública e investigación.',
      requisitos:REQ_SALUD, aliases:['bacteriologia','bacteriologo','laboratorio clinico'] },
    { id:'microbiologia', nombre:'Microbiología', titulo:'Microbiólogo(a)', snies:'52244',
      facultad:'Ciencias de la Salud, Exactas y Naturales', sedes:['Sede Principal'],
      modalidad:'Presencial', jornada:'Diurna', duracion:'8 semestres',
      costo:'$7.441.000 COP',
      resumen:'Ciencia e investigación aplicadas a alimentos, farmacia, biomedicina y ambiente.',
      requisitos:REQ_SALUD, aliases:['microbiologia','microbiologo'] },
    { id:'instrumentacion', nombre:'Instrumentación Quirúrgica', titulo:'Instrumentador(a) Quirúrgico(a)', snies:'3439',
      facultad:'Ciencias de la Salud, Exactas y Naturales', sedes:['Sede Principal'],
      modalidad:'Presencial', jornada:'Diurna', duracion:'8 semestres',
      costo:'$5.664.000 COP',
      resumen:'Asistencia en cirugías, centrales de esterilización y gestión de áreas quirúrgicas.',
      requisitos:REQ_SALUD, aliases:['instrumentacion','instrumentador','quirurgic','cirugia'] },
    { id:'derecho', nombre:'Derecho', titulo:'Abogado(a)', snies:'1498',
      facultad:'Derecho, Ciencias Políticas y Sociales', sedes:['Sede Principal','Sede Centro'],
      modalidad:'Presencial', jornada:'Diurna y nocturna', duracion:'10 semestres',
      costo:'$5.910.000 COP',
      resumen:'Programa acreditado en alta calidad, para quien disfruta el debate, la argumentación y la justicia. La admisión incluye examen y entrevista.',
      requisitos:['Formulario de inscripción (gratuito)','Fotocopia del documento de identidad','Examen y entrevista de admisión'],
      aliases:['derecho','abogad','leyes','juridic'] },
    { id:'sistemas', nombre:'Ingeniería de Sistemas', titulo:'Ingeniero(a) de Sistemas', snies:'53413',
      facultad:'Ingeniería', sedes:['Sede Centro'],
      modalidad:'Presencial', jornada:'Diurna', duracion:'8 semestres',
      costo:'$5.418.000 COP',
      resumen:'Programación, bases de datos, redes y seguridad informática.',
      requisitos:REQ_GENERAL, aliases:['ingenieria de sistemas','sistemas','software','programacion','informatica','computador'] },
    { id:'industrial', nombre:'Ingeniería Industrial', titulo:'Ingeniero(a) Industrial', snies:'4382',
      facultad:'Ingeniería', sedes:['Sede Centro'],
      modalidad:'Presencial', jornada:'Diurna y nocturna', duracion:'8 semestres',
      costo:'$5.621.000 COP',
      resumen:'Programa acreditado en alta calidad: mejora de procesos, producción, calidad y cadena de suministro.',
      requisitos:REQ_GENERAL, aliases:['ingenieria industrial','industrial'] },
    { id:'contaduria', nombre:'Contaduría Pública', titulo:'Contador(a) Público(a)', snies:'3437',
      facultad:'Ciencias Económicas, Administrativas y Contables', sedes:['Sede Centro'],
      modalidad:'Presencial (también existe en modalidad virtual)', jornada:'Diurna y nocturna', duracion:'8 semestres',
      costo:'$3.986.000 COP',
      resumen:'Programa acreditado en alta calidad: contabilidad, finanzas, impuestos y auditoría.',
      requisitos:REQ_GENERAL, aliases:['contaduria','contador','contabilidad','contable'] },
    { id:'negocios', nombre:'Administración de Negocios Internacionales', titulo:'Administrador(a) de Negocios Internacionales', snies:'54529',
      facultad:'Ciencias Económicas, Administrativas y Contables', sedes:['Sede Centro'],
      modalidad:'Presencial', jornada:'Diurna y nocturna', duracion:'8 semestres',
      costo:'$4.469.000 COP',
      resumen:'Comercio exterior, negociación e internacionalización de empresas.',
      requisitos:REQ_GENERAL, aliases:['negocios internacionales','comercio exterior','negocios','exportac','importac'] },
    { id:'logistica', nombre:'Administración Logística', titulo:'Administrador(a) Logístico(a)', snies:'',
      facultad:'Ciencias Económicas, Administrativas y Contables', sedes:['Sede Centro'],
      modalidad:'Presencial', jornada:'Diurna y nocturna', duracion:'8 semestres',
      costo:'$3.943.056 COP',
      resumen:'Programa acreditado en alta calidad: inventarios, transporte, puertos y redes de distribución.',
      requisitos:REQ_GENERAL, aliases:['logistica','logistico','cadena de suministro','puertos'] }
  ];
})();
