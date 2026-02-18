"""
ASTM Standard Specification PDF Generator
Generates ASTM-compliant specification documents for products
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib import colors
from datetime import datetime
import os
import tempfile
from io import BytesIO


class ASTMSpecGenerator:
    """Generates ASTM-compliant specification PDFs"""
    
    def __init__(self, output_dir="output_pdfs", workspace_client=None):
        self.output_dir = output_dir
        self.is_uc_volume = output_dir.startswith("/Volumes/")
        self.workspace_client = workspace_client
        
        # Only create local directories, not UC Volume paths
        if not self.is_uc_volume:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
        
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()
    
    def _create_custom_styles(self):
        """Create custom styles for ASTM documents"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ASTMTitle',
            parent=self.styles['Heading1'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=12,
            fontName='Helvetica-Bold'
        ))
        
        # Section heading style
        self.styles.add(ParagraphStyle(
            name='ASTMSection',
            parent=self.styles['Heading2'],
            fontSize=11,
            fontName='Helvetica-Bold',
            spaceAfter=6,
            spaceBefore=12
        ))
        
        # Subsection style
        self.styles.add(ParagraphStyle(
            name='ASTMSubsection',
            parent=self.styles['Heading3'],
            fontSize=10,
            fontName='Helvetica-Bold',
            spaceAfter=6,
            spaceBefore=6
        ))
        
        # Body text style
        self.styles.add(ParagraphStyle(
            name='ASTMBody',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceAfter=6
        ))
    
    def generate_specification(self, product_data, filename):
        """Generate a complete ASTM specification document"""
        # For UC Volumes, generate to temp file then upload
        if self.is_uc_volume:
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Generate PDF to temp file
            doc = SimpleDocTemplate(temp_path, pagesize=letter,
                                  rightMargin=72, leftMargin=72,
                                  topMargin=72, bottomMargin=18)
            
            story = self._build_story(product_data)
            doc.build(story)
            
            # Upload to Databricks Volume
            volume_path = f"{self.output_dir}/{filename}"
            self._upload_to_volume(temp_path, volume_path)
            
            # Clean up temp file
            os.unlink(temp_path)
            print(f"Generated and uploaded: {volume_path}")
        else:
            # Generate directly to local directory
            filepath = os.path.join(self.output_dir, filename)
            doc = SimpleDocTemplate(filepath, pagesize=letter,
                                  rightMargin=72, leftMargin=72,
                                  topMargin=72, bottomMargin=18)
            
            story = self._build_story(product_data)
            doc.build(story)
            print(f"Generated: {filepath}")
    
    def _build_story(self, product_data):
        """Build the PDF story elements"""
        story = []
        
        # Header
        story.extend(self._create_header(product_data))
        
        # 1. Scope
        story.extend(self._create_scope(product_data))
        
        # 2. Referenced Documents
        story.extend(self._create_referenced_documents(product_data))
        
        # 3. Terminology
        story.extend(self._create_terminology(product_data))
        
        # 4. Classification
        story.extend(self._create_classification(product_data))
        
        # 5. Ordering Information
        story.extend(self._create_ordering_info(product_data))
        
        # 6. Materials and Manufacture
        story.extend(self._create_materials(product_data))
        
        # 7. Chemical Composition (if applicable)
        if product_data.get('chemical_composition'):
            story.extend(self._create_chemical_composition(product_data))
        
        # 8. Mechanical and Physical Requirements
        story.extend(self._create_requirements(product_data))
        
        # 9. Dimensions and Permissible Variations
        story.extend(self._create_dimensions(product_data))
        
        # 10. Workmanship, Finish, and Appearance
        story.extend(self._create_workmanship(product_data))
        
        # 11. Sampling
        story.extend(self._create_sampling(product_data))
        
        # 12. Test Methods
        story.extend(self._create_test_methods(product_data))
        
        # 13. Inspection
        story.extend(self._create_inspection(product_data))
        
        # 14. Rejection and Rehearing
        story.extend(self._create_rejection(product_data))
        
        # 15. Certification
        story.extend(self._create_certification(product_data))
        
        # 16. Product Marking
        story.extend(self._create_product_marking(product_data))
        
        # 17. Packaging and Package Marking
        story.extend(self._create_packaging(product_data))
        
        # 18. Keywords
        story.extend(self._create_keywords(product_data))
        
        return story
    
    def _upload_to_volume(self, local_path, volume_path):
        """Upload a file to Databricks Volume using Files API"""
        if not self.workspace_client:
            raise ValueError("WorkspaceClient is required to upload to UC Volumes")
        
        # Read file contents and wrap in BytesIO for seekable interface
        with open(local_path, 'rb') as f:
            file_contents = f.read()
        
        file_like = BytesIO(file_contents)
        
        # Upload using Files API
        # The path format should be /Volumes/catalog/schema/volume/filename
        self.workspace_client.files.upload(volume_path, file_like, overwrite=True)
    
    def _create_header(self, data):
        """Create document header"""
        elements = []
        
        # ASTM designation
        elements.append(Paragraph(
            f"<b>Designation: {data['designation']}</b>",
            self.styles['ASTMTitle']
        ))
        
        # Title
        elements.append(Paragraph(
            f"<b>{data['title']}</b>",
            self.styles['ASTMTitle']
        ))
        
        # Metadata
        elements.append(Paragraph(
            f"<i>This standard was issued on {data['issue_date']}; "
            f"the version of record is continuously maintained.</i>",
            self.styles['Normal']
        ))
        elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _create_scope(self, data):
        """Create Scope section"""
        elements = []
        elements.append(Paragraph("<b>1. Scope</b>", self.styles['ASTMSection']))
        elements.append(Paragraph(
            f"1.1 This specification covers {data['scope']}",
            self.styles['ASTMBody']
        ))
        elements.append(Paragraph(
            f"1.2 The {data['product_name']} covered by this specification "
            f"are intended for use in {data['intended_use']}.",
            self.styles['ASTMBody']
        ))
        elements.append(Paragraph(
            "1.3 The values stated in SI units are to be regarded as standard. "
            "No other units of measurement are included in this standard.",
            self.styles['ASTMBody']
        ))
        elements.append(Paragraph(
            "1.4 This standard does not purport to address all of the safety concerns, "
            "if any, associated with its use. It is the responsibility of the user of "
            "this standard to establish appropriate safety, health, and environmental "
            "practices and determine the applicability of regulatory limitations prior to use.",
            self.styles['ASTMBody']
        ))
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_referenced_documents(self, data):
        """Create Referenced Documents section"""
        elements = []
        elements.append(Paragraph("<b>2. Referenced Documents</b>", self.styles['ASTMSection']))
        elements.append(Paragraph("<b>2.1 ASTM Standards:</b>", self.styles['ASTMSubsection']))
        
        for ref in data['referenced_standards']:
            elements.append(Paragraph(f"&nbsp;&nbsp;{ref}", self.styles['ASTMBody']))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_terminology(self, data):
        """Create Terminology section"""
        elements = []
        elements.append(Paragraph("<b>3. Terminology</b>", self.styles['ASTMSection']))
        elements.append(Paragraph("<b>3.1 Definitions:</b>", self.styles['ASTMSubsection']))
        
        for term, definition in data['terminology'].items():
            elements.append(Paragraph(
                f"<b>3.1.{list(data['terminology'].keys()).index(term) + 1} {term}</b>—{definition}",
                self.styles['ASTMBody']
            ))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_classification(self, data):
        """Create Classification section"""
        elements = []
        elements.append(Paragraph("<b>4. Classification</b>", self.styles['ASTMSection']))
        elements.append(Paragraph(
            f"4.1 {data['product_name']} shall be classified according to {data['classification_basis']}.",
            self.styles['ASTMBody']
        ))
        
        for i, class_type in enumerate(data['classifications'], 1):
            elements.append(Paragraph(
                f"4.1.{i} <b>{class_type['name']}</b>—{class_type['description']}",
                self.styles['ASTMBody']
            ))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_ordering_info(self, data):
        """Create Ordering Information section"""
        elements = []
        elements.append(Paragraph("<b>5. Ordering Information</b>", self.styles['ASTMSection']))
        elements.append(Paragraph(
            "5.1 Orders for material under this specification shall include the following information:",
            self.styles['ASTMBody']
        ))
        
        for i, info in enumerate(data['ordering_info'], 1):
            elements.append(Paragraph(f"5.1.{i} {info}", self.styles['ASTMBody']))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_materials(self, data):
        """Create Materials and Manufacture section"""
        elements = []
        elements.append(Paragraph("<b>6. Materials and Manufacture</b>", self.styles['ASTMSection']))
        
        for i, material in enumerate(data['materials'], 1):
            elements.append(Paragraph(f"6.{i} {material}", self.styles['ASTMBody']))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_chemical_composition(self, data):
        """Create Chemical Composition section"""
        elements = []
        elements.append(Paragraph("<b>7. Chemical Composition</b>", self.styles['ASTMSection']))
        elements.append(Paragraph(
            "7.1 The material shall conform to the chemical composition requirements "
            "specified in Table 1.",
            self.styles['ASTMBody']
        ))
        
        # Create table
        table_data = [['Element', 'Composition, %']]
        for element, comp in data['chemical_composition'].items():
            table_data.append([element, comp])
        
        table = Table(table_data, colWidths=[2*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_requirements(self, data):
        """Create Requirements section"""
        elements = []
        section_num = 8 if data.get('chemical_composition') else 7
        
        elements.append(Paragraph(
            f"<b>{section_num}. Mechanical and Physical Requirements</b>",
            self.styles['ASTMSection']
        ))
        
        # Create requirements table
        table_data = [['Property', 'Requirement', 'Test Method']]
        for req in data['requirements']:
            table_data.append([req['property'], req['value'], req['test_method']])
        
        table = Table(table_data, colWidths=[2*inch, 1.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_dimensions(self, data):
        """Create Dimensions section"""
        elements = []
        section_num = 9 if data.get('chemical_composition') else 8
        
        elements.append(Paragraph(
            f"<b>{section_num}. Dimensions and Permissible Variations</b>",
            self.styles['ASTMSection']
        ))
        
        for i, dim in enumerate(data['dimensions'], 1):
            elements.append(Paragraph(
                f"{section_num}.{i} {dim}",
                self.styles['ASTMBody']
            ))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_workmanship(self, data):
        """Create Workmanship section"""
        elements = []
        section_num = 10 if data.get('chemical_composition') else 9
        
        elements.append(Paragraph(
            f"<b>{section_num}. Workmanship, Finish, and Appearance</b>",
            self.styles['ASTMSection']
        ))
        elements.append(Paragraph(
            f"{section_num}.1 {data['workmanship']}",
            self.styles['ASTMBody']
        ))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_sampling(self, data):
        """Create Sampling section"""
        elements = []
        section_num = 11 if data.get('chemical_composition') else 10
        
        elements.append(Paragraph(
            f"<b>{section_num}. Sampling</b>",
            self.styles['ASTMSection']
        ))
        elements.append(Paragraph(
            f"{section_num}.1 {data['sampling']}",
            self.styles['ASTMBody']
        ))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_test_methods(self, data):
        """Create Test Methods section"""
        elements = []
        section_num = 12 if data.get('chemical_composition') else 11
        
        elements.append(Paragraph(
            f"<b>{section_num}. Test Methods</b>",
            self.styles['ASTMSection']
        ))
        
        for i, method in enumerate(data['test_methods'], 1):
            elements.append(Paragraph(
                f"{section_num}.{i} <b>{method['property']}</b>—{method['description']}",
                self.styles['ASTMBody']
            ))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_inspection(self, data):
        """Create Inspection section"""
        elements = []
        section_num = 13 if data.get('chemical_composition') else 12
        
        elements.append(Paragraph(
            f"<b>{section_num}. Inspection</b>",
            self.styles['ASTMSection']
        ))
        elements.append(Paragraph(
            f"{section_num}.1 Inspection of the material shall be made as agreed upon between "
            "the purchaser and the seller as part of the purchase contract.",
            self.styles['ASTMBody']
        ))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_rejection(self, data):
        """Create Rejection and Rehearing section"""
        elements = []
        section_num = 14 if data.get('chemical_composition') else 13
        
        elements.append(Paragraph(
            f"<b>{section_num}. Rejection and Rehearing</b>",
            self.styles['ASTMSection']
        ))
        elements.append(Paragraph(
            f"{section_num}.1 Material that fails to conform to the requirements of this "
            "specification may be rejected. Rejection should be reported to the producer or "
            "supplier promptly and in writing.",
            self.styles['ASTMBody']
        ))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_certification(self, data):
        """Create Certification section"""
        elements = []
        section_num = 15 if data.get('chemical_composition') else 14
        
        elements.append(Paragraph(
            f"<b>{section_num}. Certification</b>",
            self.styles['ASTMSection']
        ))
        elements.append(Paragraph(
            f"{section_num}.1 A manufacturer's or supplier's certification shall be furnished "
            "to the purchaser that the material was manufactured, sampled, tested, and inspected "
            "in accordance with this specification and has met the requirements.",
            self.styles['ASTMBody']
        ))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_product_marking(self, data):
        """Create Product Marking section"""
        elements = []
        section_num = 16 if data.get('chemical_composition') else 15
        
        elements.append(Paragraph(
            f"<b>{section_num}. Product Marking</b>",
            self.styles['ASTMSection']
        ))
        elements.append(Paragraph(
            f"{section_num}.1 {data['product_marking']}",
            self.styles['ASTMBody']
        ))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_packaging(self, data):
        """Create Packaging section"""
        elements = []
        section_num = 17 if data.get('chemical_composition') else 16
        
        elements.append(Paragraph(
            f"<b>{section_num}. Packaging and Package Marking</b>",
            self.styles['ASTMSection']
        ))
        elements.append(Paragraph(
            f"{section_num}.1 {data['packaging']}",
            self.styles['ASTMBody']
        ))
        
        elements.append(Spacer(1, 0.15*inch))
        return elements
    
    def _create_keywords(self, data):
        """Create Keywords section"""
        elements = []
        section_num = 18 if data.get('chemical_composition') else 17
        
        elements.append(Paragraph(
            f"<b>{section_num}. Keywords</b>",
            self.styles['ASTMSection']
        ))
        elements.append(Paragraph(
            f"{section_num}.1 {'; '.join(data['keywords'])}",
            self.styles['ASTMBody']
        ))
        
        return elements


if __name__ == "__main__":
    print("ASTM Specification PDF Generator initialized.")
    print("Use generate_all_pdfs.py to generate all product specifications.")

