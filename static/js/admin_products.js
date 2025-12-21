// Persian admin JS: dynamic attributes/variants, SKU generation, preview and validation

function addAttributeRow() {
  const tpl = document.getElementById('attributeRowTemplate');
  const node = tpl.content.cloneNode(true);
  document.getElementById('attributesContainer').appendChild(node);
}

function removeAttributeRow(btn) {
  const row = btn.closest('.attribute-row');
  if (row) row.remove();
}

function addVariantRow() {
  const tpl = document.getElementById('variantRowTemplate');
  const node = tpl.content.cloneNode(true);
  const tr = node.querySelector('tr');
  // set default SKU hint when size changes
  const sizeInput = tr.querySelector('input[name="variant_size"]');
  sizeInput.addEventListener('input', function(){ updateSKUHint(sizeInput); });
  document.getElementById('variantsContainer').appendChild(node);
}

function removeVariantRow(btn) {
  const tr = btn.closest('tr');
  if (tr) tr.remove();
}

async function generateSKU(productName, size) {
  try {
    const resp = await fetch('/admin/api/generate-sku', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({product_name: productName, size: size})
    });
    const data = await resp.json();
    return data.sku;
  } catch (e) {
    console.error(e); return productName.replace(/\s+/g,'-').toUpperCase() + '-' + size;
  }
}

async function updateSKUHint(sizeInput){
  const tr = sizeInput.closest('tr');
  const skuInput = tr.querySelector('input[name="variant_sku"]');
  const productName = document.getElementById('product_name') ? document.getElementById('product_name').value : '';
  const suggested = await generateSKU(productName, sizeInput.value);
  if (skuInput && !skuInput.value) {
    skuInput.value = suggested;
  } else {
    // show temporary hint (can be extended)
  }
}

async function checkSKUAvailability(sku){
  const resp = await fetch('/admin/api/check-sku', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({sku})});
  const data = await resp.json();
  return data.available;
}

function previewImage(input){
  const file = input.files && input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e){
    let img = input.closest('form').querySelector('.image-preview');
    if (!img){
      img = document.createElement('img'); img.className = 'image-preview mt-2'; img.style.maxWidth='200px';
      input.parentNode.appendChild(img);
    }
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function validateProductForm(){
  const productName = document.getElementById('product_name');
  if (!productName || !productName.value.trim()){
    alert('نام محصول الزامی است'); return false;
  }
  const variantSKUs = Array.from(document.querySelectorAll('input[name="variant_sku"]')).map(i=>i.value.trim()).filter(Boolean);
  if (variantSKUs.length === 0){
    alert('حداقل یک واریانت باید اضافه شود'); return false;
  }
  // check SKU duplicates
  const skuSet = new Set();
  for (const s of variantSKUs){
    if (skuSet.has(s)) { alert('SKU تکراری یافت شد: ' + s); return false; }
    skuSet.add(s);
  }
  return true;
}

function updatePreview(){
  const name = document.getElementById('product_name') ? document.getElementById('product_name').value : '';
  const brandSel = document.querySelector('select[name="brand_id"]');
  const brand = brandSel ? (brandSel.options[brandSel.selectedIndex].text) : '';
  const catSel = document.querySelector('select[name="category_id"]');
  const cat = catSel ? (catSel.options[catSel.selectedIndex].text) : '';
  const attrs = Array.from(document.querySelectorAll('.attribute-row')).map(r=>{
    const k = r.querySelector('select[name="attribute_id"]');
    const v = r.querySelector('input[name="attribute_value"]');
    return (k && v) ? `${k.options[k.selectedIndex].text}: ${v.value}` : '';
  }).filter(Boolean);
  const variants = Array.from(document.querySelectorAll('#variantsContainer tr')).map(tr=>{
    const sku = tr.querySelector('input[name="variant_sku"]').value;
    const size = tr.querySelector('input[name="variant_size"]').value;
    const price = tr.querySelector('input[name="variant_retail"]').value;
    return `${sku} — ${size} — ${price}`;
  });

  const el = document.getElementById('reviewSummary');
  if (!el) return;
  el.innerHTML = `<div class="card p-3"><h6>${name}</h6><div>برند: ${brand}</div><div>دسته: ${cat}</div><hr><div><strong>مشخصات:</strong><br>${attrs.join('<br>')}</div><hr><div><strong>واریانت‌ها:</strong><br>${variants.join('<br>')}</div></div>`;
}

// wire events
document.addEventListener('input', function(e){
  if (e.target && (e.target.name === 'attribute_value' || e.target.name === 'attribute_id' || e.target.name === 'product_name' || e.target.name.startsWith('variant_'))) {
    updatePreview();
  }
});

// attach form submit validation
const form = document.getElementById('productForm');
if (form){
  form.addEventListener('submit', function(e){
    if (!validateProductForm()){ e.preventDefault(); }
  });
}
